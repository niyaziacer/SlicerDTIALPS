import csv
import functools
import os

import numpy as np
import nibabel as nib

try:
    import slicer
    import qt
    import ctk
    from slicer.ScriptedLoadableModule import (
        ScriptedLoadableModule,
        ScriptedLoadableModuleWidget,
        ScriptedLoadableModuleLogic,
        ScriptedLoadableModuleTest,
    )
except ImportError:
    # Slicer disinda (orn. plain python3 ile test) da import edilebilmesi icin
    # minimal yerel taban siniflar. Slicer icinde calisirken bu blok hic
    # devreye girmez, gercek Slicer siniflari kullanilir.
    slicer = None
    qt = None
    ctk = None

    class ScriptedLoadableModule:
        def __init__(self, parent):
            self.parent = parent

    class ScriptedLoadableModuleWidget:
        def __init__(self, parent=None):
            self.parent = parent

        def setup(self):
            pass

    class ScriptedLoadableModuleLogic:
        pass

    class ScriptedLoadableModuleTest:
        def setUp(self):
            pass

        def runTest(self):
            pass


class DTIALPS(ScriptedLoadableModule):
    """Modul kayit sinifi (Slicer modul listesinde gorunen meta bilgiler)."""

    def __init__(self, parent):
        super().__init__(parent)
        parent.title = "DTI-ALPS"
        parent.categories = ["Diffusion"]
        parent.contributors = ["Niyazi Acer (Erciyes University)"]
        parent.helpText = (
            "Computes the DTI-ALPS (Diffusion Tensor Image Analysis along the "
            "Perivascular Space) index from DSI Studio QSDR output.<br><br>"
            "<b>Data preparation (DSI Studio):</b> DICOM/NIfTI &rarr; SRC &rarr; "
            "Reconstruction with <b>QSDR</b> (not GQI/DTI), template human 2mm, "
            "output metrics tensor+fa+md &rarr; export txx, tyy, tzz, dti_fa, md "
            "as NIfTI. <b>QSDR is required</b>: ROIs are placed at fixed MNI "
            "coordinates, which are only valid in normalized (template) space, "
            "not native subject space.<br><br>"
            "<b>Usage:</b> load each volume with its \"...\" button "
            "(txx/tyy/tzz/FA required, MD optional), then click Apply for "
            "left/right/mean ALPS, a per-ROI table, and automatic ROI markups. "
            "The module warns rather than silently passing bad data: it flags "
            "out-of-range MD/ALPS, wrong dominant axis, or low ROI voxel counts. "
            "See the extension's README.md for full details and data-suitability "
            "criteria."
        )
        parent.acknowledgementText = (
            "ALPS method: Taoka et al., Jpn J Radiol 2017. "
            "ROI coordinates: Barisano/Liu."
        )


class DTIALPSWidget(ScriptedLoadableModuleWidget):
    """Girdi secimi (sahneden veya dosyadan), Apply, sonuc tablosu ve ROI markup'lari."""

    REQUIRED_KEYS = ("txx", "tyy", "tzz", "fa")
    ALL_KEYS = ("txx", "tyy", "tzz", "fa", "md")
    LABELS = {
        "txx": "Dxx (txx)",
        "tyy": "Dyy (tyy)",
        "tzz": "Dzz (tzz)",
        "fa": "FA",
        "md": "MD (optional)",
    }
    ROI_NAMES = ("proj_L", "proj_R", "assoc_L", "assoc_R")
    ROI_COLORS = {
        "proj_L": (1.0, 0.0, 0.0),
        "proj_R": (1.0, 0.0, 0.0),
        "assoc_L": (0.0, 1.0, 1.0),
        "assoc_R": (0.0, 1.0, 1.0),
    }

    def setup(self):
        super().setup()

        self.logic = DTIALPSLogic()
        self.nodeSelectors = {}
        self._roiNodes = {}
        # functools.partial nesnelerini burada sakliyoruz: connect'e verilen
        # callable'a self disinda hicbir yerde referans tutulmazsa, PythonQt
        # bazi surumlerde bagliyi sessizce dusurebiliyor (GC). Bu sozluk
        # widget'in omru boyunca callable'i canli tutuyor.
        self._loadHandlers = {}

        inputsCollapsible = ctk.ctkCollapsibleButton()
        inputsCollapsible.text = "Input Volumes"
        self.layout.addWidget(inputsCollapsible)
        formLayout = qt.QFormLayout(inputsCollapsible)

        for key in self.ALL_KEYS:
            rowWidget = qt.QWidget()
            rowLayout = qt.QHBoxLayout(rowWidget)
            rowLayout.setContentsMargins(0, 0, 0, 0)

            selector = slicer.qMRMLNodeComboBox()
            selector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
            selector.addEnabled = False
            selector.removeEnabled = False
            # Zorunlu seciciler de dahil hepsinde noneEnabled=True: sahneye ilk
            # volum eklendiginde bos seciciler onu otomatik secmesin diye.
            # Apply zaten currentNode() None kontrolu yapiyor.
            selector.noneEnabled = True
            selector.setMRMLScene(slicer.mrmlScene)
            selector.connect("currentNodeChanged(vtkMRMLNode*)", self._updateApplyButtonState)
            self.nodeSelectors[key] = selector
            rowLayout.addWidget(selector)

            # ctkPathLineEdit tamamen terk edildi: currentPathChanged sinyali
            # bu ctk surumunde Python'a hic ulasmiyordu (string connect,
            # attribute connect, referans-saklayan functools.partial - ucu de
            # denendi, hicbiri calismadi). Basit bir QPushButton + QFileDialog
            # + QPushButton.clicked kullaniliyor - clicked PythonQt'ta guvenilir.
            loadButton = qt.QPushButton("...")
            loadButton.setMaximumWidth(30)
            handler = functools.partial(self._onLoadClicked, key=key)
            self._loadHandlers[key] = handler
            loadButton.clicked.connect(handler)
            rowLayout.addWidget(loadButton)

            formLayout.addRow(self.LABELS[key], rowWidget)

        self.applyButton = qt.QPushButton("Apply")
        self.applyButton.enabled = False
        self.applyButton.connect("clicked(bool)", self.onApplyClicked)
        self.layout.addWidget(self.applyButton)

        self.exportCsvButton = qt.QPushButton("Save as CSV")
        self.exportCsvButton.enabled = False
        self.exportCsvButton.connect("clicked(bool)", self.onExportCsvClicked)
        self.layout.addWidget(self.exportCsvButton)

        resultsCollapsible = ctk.ctkCollapsibleButton()
        resultsCollapsible.text = "Results"
        self.layout.addWidget(resultsCollapsible)
        resultsLayout = qt.QVBoxLayout(resultsCollapsible)

        bigFont = qt.QFont()
        bigFont.setPointSize(18)
        bigFont.setBold(True)

        self.alpsLLabel = qt.QLabel("ALPS Left: —")
        self.alpsRLabel = qt.QLabel("ALPS Right: —")
        self.alpsMeanLabel = qt.QLabel("ALPS Mean: —")
        for label in (self.alpsLLabel, self.alpsRLabel, self.alpsMeanLabel):
            label.setFont(bigFont)
            resultsLayout.addWidget(label)

        self.resultsTable = qt.QTableWidget(len(self.ROI_NAMES), 9)
        self.resultsTable.setHorizontalHeaderLabels(
            ["ROI", "Dxx", "Dyy", "Dzz", "FA", "n", "Dominant Axis", "Expected Axis", "Match"]
        )
        self.resultsTable.verticalHeader().setVisible(False)
        for row, name in enumerate(self.ROI_NAMES):
            self.resultsTable.setItem(row, 0, qt.QTableWidgetItem(name))
        resultsLayout.addWidget(self.resultsTable)

        self.warningsTextEdit = qt.QTextEdit()
        self.warningsTextEdit.setReadOnly(True)
        self.warningsTextEdit.setPlainText("—")
        resultsLayout.addWidget(self.warningsTextEdit)

        self.layout.addStretch(1)

        self._lastResult = None
        self._lastWarnings = None
        self._lastNodes = None

        self._updateApplyButtonState()

    def _updateApplyButtonState(self, node=None):
        ready = all(
            self.nodeSelectors[key].currentNode() is not None for key in self.REQUIRED_KEYS
        )
        self.applyButton.enabled = ready

    @staticmethod
    def _normalizePath(path):
        # os.path.normcase: Windows'ta harf buyuklugu farkini de goz ardi eder
        # (normpath tek basina bunu yapmiyordu) - TAM yol birebir esitligi
        # icin tek kaynak, gevseklik/kismi eslesme YOK.
        return os.path.normcase(os.path.abspath(path))

    def _findExistingVolumeForPath(self, path):
        """Sahnede bu dosyadan zaten yuklenmis bir volume var mi diye bakar
        (storage node dosya adi karsilastirmasiyla, TAM yol esitligi) - ayni
        dosya tekrar secilirse yeniden yuklememek icin."""
        normPath = self._normalizePath(path)
        for node in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
            storageNode = node.GetStorageNode()
            if storageNode is None or not storageNode.GetFileName():
                continue
            if self._normalizePath(storageNode.GetFileName()) == normPath:
                return node
        return None

    def _nodeMatchesPath(self, node, path):
        """Node'un storage dosyasi gercekten istenen path mi - yukleme/eslestirme
        sonrasi son bir dogrulama (yanlis node sessizce atanmasin diye)."""
        storageNode = node.GetStorageNode()
        if storageNode is None or not storageNode.GetFileName():
            return False
        return self._normalizePath(storageNode.GetFileName()) == self._normalizePath(path)

    def _onLoadClicked(self, checked, key):
        path = qt.QFileDialog.getOpenFileName(
            self.parent, "Select Volume", "", "NIfTI (*.nii *.nii.gz)"
        )
        self._onPathSelected(path, key)

    def _onPathSelected(self, path, key):
        if not path:
            return

        try:
            node = self._findExistingVolumeForPath(path)
            if node is None:
                node = slicer.util.loadVolume(path)
                # loadVolume dokumantasyonu: birden fazla node yuklenirse
                # liste donebilir - tek node bekliyoruz, ilkini al.
                if isinstance(node, list):
                    node = node[0] if node else None
        except Exception as exc:
            slicer.util.errorDisplay(f"Could not load volume:\n{path}\n\n{exc}")
            return

        if node is None:
            slicer.util.errorDisplay(f"Could not load volume:\n{path}")
            return

        if not self._nodeMatchesPath(node, path):
            storageNode = node.GetStorageNode()
            actualPath = storageNode.GetFileName() if storageNode is not None else "(none)"
            slicer.util.errorDisplay(
                f"Unexpected volume assigned for the '{key}' field - assignment cancelled.\n\n"
                f"Requested file:\n{path}\n\n"
                f"Found/assigned node's file:\n{actualPath}\n\n"
                f"Please try again."
            )
            return

        self._assignNodeToSelector(key, node)

    def _assignNodeToSelector(self, key, node):
        # setCurrentNode degil setCurrentNodeID kullaniliyor: node sahneye
        # eklendikten hemen sonra secici bazen eski/otomatik-secilen node'u
        # birakmiyordu, ID uzerinden secim bunu cozuyor.
        selector = self.nodeSelectors[key]
        nodeId = node.GetID()
        selector.setCurrentNodeID(nodeId)
        if selector.currentNodeID != nodeId:
            # qMRMLNodeComboBox'in ic modeli, sahneye YENI eklenen node'u
            # henuz islememis olabilir (Qt event loop zamanlama sorunu -
            # ozellikle art arda birkac volum yuklendiginde). Bir sonraki
            # event dongusune erteleyip tekrar dene.
            qt.QTimer.singleShot(0, lambda: selector.setCurrentNodeID(nodeId))

    def _buildWarnings(self, result):
        """Sonuc dict'ini QC esikleriyle (Logic'teki sabitler) karsilastirip
        okunabilir uyari/bilgi metinleri uretir. Saf metin uretimi - Logic'e
        dokunmaz, hesap yapmaz."""
        logic = self.logic
        warnings = []

        if result["md_mean"] is not None and not (
            logic.MD_MIN <= result["md_mean"] <= logic.MD_MAX
        ):
            warnings.append(
                f"WARNING: Mean MD ({result['md_mean']:.3f}) is outside the "
                f"physiological range (0.6-1.2 x10^-3). Check reconstruction/"
                f"normalization quality. ALPS value may be unreliable."
            )

        if not (logic.ALPS_MIN <= result["alps_mean"] <= logic.ALPS_MAX):
            warnings.append(
                f"WARNING: Mean ALPS ({result['alps_mean']:.3f}) is outside the "
                f"literature range (0.9-1.8). Verify data quality and ROI "
                f"positions."
            )

        for name in self.ROI_NAMES:
            roi = result["rois"][name]
            if not roi["axis_ok"]:
                warnings.append(
                    f"WARNING: In the {name} ROI, the dominant axis is "
                    f"{roi['dominant_axis']} instead of the expected "
                    f"{roi['expected_axis']}. The ROI position or image space "
                    f"may be incorrect."
                )

        if result["fa_rescaled"]:
            warnings.append(
                "INFO: FA was automatically rescaled to the 0-1 range (source "
                "data was on a 0-1000 scale)."
            )

        for name in self.ROI_NAMES:
            roi = result["rois"][name]
            if roi["n"] < logic.MIN_ROI_VOXELS:
                warnings.append(
                    f"WARNING: Only {roi['n']} voxels passed the FA threshold "
                    f"in the {name} ROI. Result is unreliable."
                )

        if not warnings:
            warnings.append("All checks passed.")

        return warnings

    def onApplyClicked(self, checked=False):
        nodes = {key: self.nodeSelectors[key].currentNode() for key in self.ALL_KEYS}
        result = self.logic.computeALPSFromNodes(
            nodes["txx"], nodes["tyy"], nodes["tzz"], nodes["fa"], nodes["md"]
        )

        self.alpsLLabel.text = f"ALPS Left: {result['alps_L']:.4f}"
        self.alpsRLabel.text = f"ALPS Right: {result['alps_R']:.4f}"
        self.alpsMeanLabel.text = f"ALPS Mean: {result['alps_mean']:.4f}"

        redBrush = qt.QBrush(qt.QColor(255, 180, 180))
        for row, name in enumerate(self.ROI_NAMES):
            roi = result["rois"][name]
            values = [
                f"{roi['Dxx']:.6f}",
                f"{roi['Dyy']:.6f}",
                f"{roi['Dzz']:.6f}",
                f"{roi['FA']:.3f}",
                str(roi["n"]),
                roi["dominant_axis"],
                roi["expected_axis"],
                str(roi["axis_ok"]),
            ]
            for col, value in enumerate(values, start=1):
                item = qt.QTableWidgetItem(value)
                if not roi["axis_ok"]:
                    item.setBackground(redBrush)
                self.resultsTable.setItem(row, col, item)
            if not roi["axis_ok"]:
                nameItem = self.resultsTable.item(row, 0)
                nameItem.setBackground(redBrush)

        warnings = self._buildWarnings(result)
        self.warningsTextEdit.setPlainText("\n".join(warnings))

        self._updateROIMarkups(result["rois"])

        self._lastResult = result
        self._lastWarnings = warnings
        self._lastNodes = nodes
        self.exportCsvButton.enabled = True

    def _updateROIMarkups(self, rois):
        for node in self._roiNodes.values():
            if node is not None and slicer.mrmlScene.IsNodePresent(node):
                slicer.mrmlScene.RemoveNode(node)
        self._roiNodes = {}

        for name in self.ROI_NAMES:
            roi = rois[name]
            roiNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLMarkupsROINode", f"DTIALPS_{name}"
            )
            roiNode.SetCenter(*roi["center_ras"])
            size = 2 * roi["radius_mm"]
            roiNode.SetSize(size, size, size)
            roiNode.SetLocked(True)
            displayNode = roiNode.GetDisplayNode()
            if displayNode is not None:
                color = self.ROI_COLORS[name]
                displayNode.SetColor(*color)
                displayNode.SetSelectedColor(*color)
                # Sade gorunum: isim/properties etiketleri ve resize/rotate
                # tutamaclari (kontrol noktalari) gizli, sadece kutu/sekil
                # gorunsun. Kesitlerde gorunen "DTIALPS_assoc_R" gibi yazi
                # PointLabelsVisibility degil, PropertiesLabelVisibility ile
                # kontrol ediliyor (Slicer'in kendi AddManyMarkupsFiducialTest.py
                # test dosyasinda dogrulandi).
                displayNode.SetPropertiesLabelVisibility(False)
                displayNode.SetPointLabelsVisibility(False)
                if hasattr(displayNode, "SetHandlesInteractive"):
                    displayNode.SetHandlesInteractive(False)
            self._roiNodes[name] = roiNode

    def onExportCsvClicked(self, checked=False):
        if self._lastResult is None:
            return

        defaultPath = os.path.join(os.path.expanduser("~"), "DTIALPS_result.csv")
        path = qt.QFileDialog.getSaveFileName(
            self.parent, "Save as CSV", defaultPath, "CSV (*.csv)"
        )
        if not path:
            return

        result = self._lastResult
        nodes = self._lastNodes

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow(["Metric", "Value"])
            writer.writerow(["ALPS_Left", f"{result['alps_L']:.6f}"])
            writer.writerow(["ALPS_Right", f"{result['alps_R']:.6f}"])
            writer.writerow(["ALPS_Mean", f"{result['alps_mean']:.6f}"])
            writer.writerow(["FA_Rescaled", str(result["fa_rescaled"])])
            writer.writerow([])

            writer.writerow(
                ["ROI", "Dxx", "Dyy", "Dzz", "FA", "MD", "n",
                 "Dominant_Axis", "Expected_Axis", "Match"]
            )
            for name in self.ROI_NAMES:
                roi = result["rois"][name]
                writer.writerow([
                    name,
                    f"{roi['Dxx']:.6f}",
                    f"{roi['Dyy']:.6f}",
                    f"{roi['Dzz']:.6f}",
                    f"{roi['FA']:.3f}",
                    "" if roi["MD"] is None else f"{roi['MD']:.6f}",
                    roi["n"],
                    roi["dominant_axis"],
                    roi["expected_axis"],
                    roi["axis_ok"],
                ])
            writer.writerow([])

            writer.writerow(["Warnings"])
            for warning in self._lastWarnings:
                writer.writerow([warning])
            writer.writerow([])

            writer.writerow(["Input Volumes"])
            for key in self.ALL_KEYS:
                node = nodes[key]
                writer.writerow([key, node.GetName() if node is not None else "(none)"])

        slicer.util.infoDisplay(f"Saved:\n{path}")


class DTIALPSLogic(ScriptedLoadableModuleLogic):
    """DTI-ALPS hesap mantigi.

    Cekirdek hesap (_computeALPSCore) Slicer sahnesinden (MRML node) bagimsiz,
    saf numpy/affine tabanli calisir. Iki giris kapisi bu cekirdegi paylasir:
    - computeALPS: dosya yolu -> nibabel ile yukleme -> cekirdek
    - computeALPSFromNodes: MRML volume node -> Slicer array/affine cevirisi -> cekirdek
    """

    MNI_ROIS = {
        "proj_L": (-26, -16, 27),
        "proj_R": (26, -16, 27),
        "assoc_L": (-38, -16, 27),
        "assoc_R": (38, -16, 27),
    }
    ROI_RADIUS_MM = 3.0
    FA_THRESHOLD = 0.20
    FA_RESCALE_TRIGGER = 1.5

    # QC esikleri - Widget bu sabitleri okuyup uyari METNI uretir, Logic
    # sadece ham sayi + esik dondurur.
    # MD_MIN/MD_MAX x10^-3 mm^2/s cinsinden ama literal 0.6e-3/1.2e-3 DEGIL:
    # bu pipeline'in _md.nii.gz dosyalari zaten bu olcekte kaydediliyor (orn.
    # ACER'de roi MD~0.7 cikiyor, 0.0007 degil) - bkz. plan dosyasindaki not.
    MD_MIN, MD_MAX = 0.6, 1.2
    ALPS_MIN, ALPS_MAX = 0.9, 1.8
    MIN_ROI_VOXELS = 10

    def _mniToVox(self, xyz, affine):
        v = np.linalg.inv(affine) @ np.array([*xyz, 1.0])
        return np.round(v[:3]).astype(int)

    def _sphereMask(self, center, r, shape):
        zz, yy, xx = np.ogrid[: shape[2], : shape[1], : shape[0]]
        x0, y0, z0 = center
        d2 = (xx - x0) ** 2 + (yy - y0) ** 2 + (zz - z0) ** 2
        return (d2 <= r * r).transpose(2, 1, 0)

    def _roiMean(self, data, mask, fa, faThreshold):
        m = mask & (fa >= faThreshold) & (data > 1e-8)
        if m.sum() < 3:
            m = mask & (data > 1e-8)
        if not m.any():
            return float("nan"), 0
        return float(data[m].mean()), int(m.sum())

    def _computeALPSCore(self, Dxx, Dyy, Dzz, fa, affine, md=None):
        """Sadece numpy dizileri + affine alan, MRML/dosya sisteminden bagimsiz cekirdek hesap."""
        shape = Dxx.shape
        voxSize = np.abs(np.diag(affine)[:3])

        faRescaled = False
        if fa.max() > self.FA_RESCALE_TRIGGER:
            fa = fa / 1000.0
            faRescaled = True

        rVox = max(2, round(self.ROI_RADIUS_MM / voxSize.mean()))
        radiusMm = rVox * voxSize.mean()

        rois = {}
        for name, mniXYZ in self.MNI_ROIS.items():
            voxCenter = self._mniToVox(mniXYZ, affine)
            mask = self._sphereMask(voxCenter, rVox, shape)

            dxxMean, n = self._roiMean(Dxx, mask, fa, self.FA_THRESHOLD)
            dyyMean, _ = self._roiMean(Dyy, mask, fa, self.FA_THRESHOLD)
            dzzMean, _ = self._roiMean(Dzz, mask, fa, self.FA_THRESHOLD)
            faMean, _ = self._roiMean(fa, mask, fa, 0.0)
            mdMean = (
                self._roiMean(md, mask, fa, self.FA_THRESHOLD)[0]
                if md is not None
                else None
            )

            axisValues = {"Dxx": dxxMean, "Dyy": dyyMean, "Dzz": dzzMean}
            dominantAxis = max(
                axisValues,
                key=lambda k: axisValues[k] if not np.isnan(axisValues[k]) else -np.inf,
            )
            expectedAxis = "Dzz" if "proj" in name else "Dyy"

            # ROI'yi sahneye cizecek GUI kodu bu degeri DOGRUDAN kullanacak
            # (MNI koordinatini kendi basina yeniden islemeyecek) - boylece
            # cizilen ROI ile maskelemede kullanilan voksel merkezi ayni sey olur.
            centerRas = tuple(float(c) for c in (affine @ np.array([*voxCenter, 1.0]))[:3])

            rois[name] = {
                "Dxx": dxxMean,
                "Dyy": dyyMean,
                "Dzz": dzzMean,
                "FA": faMean,
                "MD": mdMean,
                "n": n,
                "dominant_axis": dominantAxis,
                "expected_axis": expectedAxis,
                "axis_ok": dominantAxis == expectedAxis,
                "center_ras": centerRas,
                "radius_mm": radiusMm,
            }

        def alpsForSide(side):
            proj, assoc = rois[f"proj_{side}"], rois[f"assoc_{side}"]
            numerator = np.nanmean([proj["Dxx"], assoc["Dxx"]])
            denominator = np.nanmean([proj["Dyy"], assoc["Dzz"]])
            return float(numerator / denominator) if denominator > 1e-10 else float("nan")

        alpsL = alpsForSide("L")
        alpsR = alpsForSide("R")
        alpsMean = float(np.nanmean([alpsL, alpsR]))

        mdMeanOverall = (
            float(np.nanmean([roi["MD"] for roi in rois.values()]))
            if md is not None
            else None
        )

        return {
            "alps_L": alpsL,
            "alps_R": alpsR,
            "alps_mean": alpsMean,
            "fa_rescaled": faRescaled,
            "md_mean": mdMeanOverall,
            "affine": affine,
            "rois": rois,
        }

    def computeALPS(self, txxPath, tyyPath, tzzPath, faPath, mdPath=None):
        """DTI-ALPS index'ini NIfTI dosya yollarindan hesaplar.

        Args:
            txxPath, tyyPath, tzzPath: DSI Studio Dxx/Dyy/Dzz tensor NIfTI yollari.
            faPath: FA NIfTI yolu.
            mdPath: opsiyonel MD NIfTI yolu (ALPS formulunu etkilemez, sadece
                per-ROI bilgi amacli eklenir).

        Returns:
            dict: {
                "alps_L": float, "alps_R": float, "alps_mean": float,
                "fa_rescaled": bool,
                "md_mean": float | None,  # 4 ROI'nin MD ortalamasi (md verilmediyse None)
                "affine": np.ndarray (4x4),
                "rois": {
                    "proj_L": {"Dxx", "Dyy", "Dzz", "FA", "MD", "n",
                               "dominant_axis", "expected_axis", "axis_ok",
                               "center_ras", "radius_mm"},
                    "proj_R": {...}, "assoc_L": {...}, "assoc_R": {...},
                },
            }
        """
        txxImg = nib.load(txxPath)
        Dxx = txxImg.get_fdata()
        Dyy = nib.load(tyyPath).get_fdata()
        Dzz = nib.load(tzzPath).get_fdata()
        fa = nib.load(faPath).get_fdata()
        md = nib.load(mdPath).get_fdata() if mdPath else None
        affine = txxImg.affine

        return self._computeALPSCore(Dxx, Dyy, Dzz, fa, affine, md)

    def _arrayAndAffineFromNode(self, node):
        """Slicer vtkMRMLScalarVolumeNode -> (nibabel-uyumlu (i,j,k) dizi, affine).

        slicer.util.arrayFromVolume (k,j,i) sirasinda doner (ITK boyut sirasinin
        tersi); nibabel ile ayni (i,j,k) sirasina getirmek icin transpose(2,1,0)
        uygulanir. Slicer'in RAS'i ile nibabel affine'inin world ekseni ayni
        yonelimde oldugundan (NIfTI world space zaten RAS) ek bir LPS/RAS
        cevirisi gerekmez.
        """
        import vtk

        arrKji = slicer.util.arrayFromVolume(node)
        arrIjk = arrKji.transpose(2, 1, 0)

        ijkToRas = vtk.vtkMatrix4x4()
        node.GetIJKToRASMatrix(ijkToRas)
        affine = slicer.util.arrayFromVTKMatrix(ijkToRas)

        return arrIjk, affine

    def computeALPSFromNodes(self, txxNode, tyyNode, tzzNode, faNode, mdNode=None):
        """DTI-ALPS index'ini Slicer sahnesindeki volume node'larindan hesaplar.

        computeALPS ile ayni cekirdegi (_computeALPSCore) kullanir; sadece
        dosya yerine sahnedeki node'lardan dizi/affine okur. Return degeri
        computeALPS ile birebir ayni yapidadir.
        """
        Dxx, affine = self._arrayAndAffineFromNode(txxNode)
        Dyy, _ = self._arrayAndAffineFromNode(tyyNode)
        Dzz, _ = self._arrayAndAffineFromNode(tzzNode)
        fa, _ = self._arrayAndAffineFromNode(faNode)
        md, _ = self._arrayAndAffineFromNode(mdNode) if mdNode is not None else (None, None)

        return self._computeALPSCore(Dxx, Dyy, Dzz, fa, affine, md)


class DTIALPSTest(ScriptedLoadableModuleTest):
    """Gercek test senaryolari bir sonraki adimda eklenecek."""

    def setUp(self):
        pass

    def runTest(self):
        pass
