import numpy as np
import pytest

import DTIALPS as M

# DSI Studio QSDR (human 2 mm) NIfTI geometrisi: 80x100x80, x/y ters
AFFINE = np.array([[-2, 0, 0, 79.5], [0, -2, 0, 81.5], [0, 0, 2, -72.0], [0, 0, 0, 1.0]])
SHAPE = (80, 100, 80)
logic = M.DTIALPSLogic()


def make_maps(proj=(0.55e-3, 0.50e-3, 1.0e-3), assoc=(0.58e-3, 1.1e-3, 0.32e-3), fa=0.5):
    Dxx = np.full(SHAPE, 0.6e-3)
    Dyy = np.full(SHAPE, 0.6e-3)
    Dzz = np.full(SHAPE, 0.6e-3)
    F = np.full(SHAPE, fa)
    for name, mni in logic.MNI_ROIS.items():
        c = logic._mniToVox(mni, AFFINE)
        sel = logic._sphereMask(c, 2, SHAPE)
        vals = proj if "proj" in name else assoc
        Dxx[sel], Dyy[sel], Dzz[sel] = vals
    return Dxx, Dyy, Dzz, F


def test_roi_voxel_centers_are_fixed():
    # gercek veride dogrulanan voksel merkezleri (MNI -> ijk)
    assert tuple(logic._mniToVox((-26, -16, 27), AFFINE)) == (53, 49, 50)
    assert tuple(logic._mniToVox((26, -16, 27), AFFINE)) == (27, 49, 50)
    assert tuple(logic._mniToVox((-38, -16, 27), AFFINE)) == (59, 49, 50)
    assert tuple(logic._mniToVox((38, -16, 27), AFFINE)) == (21, 49, 50)


def test_alps_formula_and_axes():
    Dxx, Dyy, Dzz, fa = make_maps()
    r = logic._computeALPSCore(Dxx, Dyy, Dzz, fa, AFFINE)
    expected = np.mean([0.55e-3, 0.58e-3]) / np.mean([0.50e-3, 0.32e-3])
    assert r["alps_L"] == pytest.approx(expected)
    assert r["alps_R"] == pytest.approx(expected)
    assert r["alps_mean"] == pytest.approx(expected)
    assert all(roi["axis_ok"] for roi in r["rois"].values())
    assert r["radius_mm"] == 3.0
    assert r["rois"]["proj_L"]["radius_mm"] == 3.0  # gercek mm, varsayilan 3 mm
    assert r["rois"]["proj_L"]["n"] == 19  # 2 mm vokselde: 1 + 6 + 12 voksel


def test_radius_is_real_mm_and_adjustable():
    Dxx, Dyy, Dzz, fa = make_maps()
    n = {}
    for rad in (2.0, 2.5, 3.0, 4.0):
        r = logic._computeALPSCore(Dxx, Dyy, Dzz, fa, AFFINE, radiusMm=rad)
        assert r["radius_mm"] == rad
        assert r["rois"]["assoc_R"]["radius_mm"] == rad
        n[rad] = r["rois"]["proj_L"]["n"]
    # 2 mm vokselde: r=2 -> 7 (merkez + 6 komsu), r=2.5 -> 7, r=3 -> 19, r=4 -> 33
    assert n == {2.0: 7, 2.5: 7, 3.0: 19, 4.0: 33}


def test_radius_scales_with_voxel_size():
    # 1 mm vokselde 3 mm yaricap ~113 voksel; yaricap vokselde degil mm'de
    from_mask = logic._sphereMask((10, 10, 10), 3.0, (21, 21, 21), (1.0, 1.0, 1.0))
    assert 100 < from_mask.sum() < 130
    coarse = logic._sphereMask((10, 10, 10), 3.0, (21, 21, 21), (2.0, 2.0, 2.0))
    assert coarse.sum() == 19


def test_invalid_radius_rejected():
    Dxx, Dyy, Dzz, fa = make_maps()
    with pytest.raises(ValueError):
        logic._computeALPSCore(Dxx, Dyy, Dzz, fa, AFFINE, radiusMm=0)


def test_wrong_axis_is_flagged():
    Dxx, Dyy, Dzz, fa = make_maps(proj=(0.55e-3, 1.0e-3, 0.5e-3))  # proj Dyy baskin
    r = logic._computeALPSCore(Dxx, Dyy, Dzz, fa, AFFINE)
    assert not r["rois"]["proj_L"]["axis_ok"]
    assert r["rois"]["assoc_L"]["axis_ok"]


def test_fa_rescale_x1000():
    Dxx, Dyy, Dzz, fa = make_maps()
    r = logic._computeALPSCore(Dxx, Dyy, Dzz, fa * 1000, AFFINE)
    assert r["fa_rescaled"] is True


def test_direction_color_axes():
    fa = np.full((3, 1, 1), 0.9)
    Dxx = np.array([1.0, 0.2, 0.2]).reshape(3, 1, 1)
    Dyy = np.array([0.2, 1.0, 0.2]).reshape(3, 1, 1)
    Dzz = np.array([0.2, 0.2, 1.0]).reshape(3, 1, 1)
    rgb = M.DTIALPSLogic.directionColor(Dxx, Dyy, Dzz, fa)
    assert rgb.shape == (3, 1, 1, 3) and rgb.dtype == np.uint8
    for i in range(3):
        assert rgb[i, 0, 0].argmax() == i          # R, G, B sirasiyla
        assert rgb[i, 0, 0][i] > 200


def test_direction_color_dark_when_low_fa_or_empty():
    one = np.ones((1, 1, 1))
    low = M.DTIALPSLogic.directionColor(one, 0.2 * one, 0.2 * one, 0.02 * one)
    assert low.max() < 30
    empty = M.DTIALPSLogic.directionColor(0 * one, 0 * one, 0 * one, 0.9 * one)
    assert empty.max() == 0
    nan = M.DTIALPSLogic.directionColor(np.nan * one, one, one, one)  # NaN -> cokmez
    assert nan.dtype == np.uint8


def test_direction_color_fa_rescale():
    one = np.ones((1, 1, 1))
    a = M.DTIALPSLogic.directionColor(one, 0.2 * one, 0.2 * one, 0.9 * one)
    b = M.DTIALPSLogic.directionColor(one, 0.2 * one, 0.2 * one, 900 * one)  # x1000 olcek
    assert np.array_equal(a, b)


def test_input_spread_warnings():
    ok = {k: {"path": f"/data/exp1/s05_{k}.nii.gz", "mtime": 1000.0 + i * 10} for i, k in enumerate(("txx", "tyy", "tzz", "fa", "md"))}
    assert M.inputSpreadWarnings(ok) == []
    mixed_time = dict(ok)
    mixed_time["fa"] = {"path": "/data/exp1/s05_fa.nii.gz", "mtime": 1000.0 + 14 * 86400}
    w = M.inputSpreadWarnings(mixed_time)
    assert len(w) == 1 and "apart" in w[0]
    mixed_dir = dict(ok)
    mixed_dir["md"] = {"path": "/data/exp2/s05_md.nii.gz", "mtime": 1040.0}
    w = M.inputSpreadWarnings(mixed_dir)
    assert len(w) == 1 and "different folders" in w[0]
    assert M.inputSpreadWarnings({"txx": {"path": None, "mtime": None}}) == []
