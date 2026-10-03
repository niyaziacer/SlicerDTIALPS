# SlicerDTIALPS — A 3D Slicer module for computing the DTI-ALPS index

## Description

SlicerDTIALPS automatically computes the DTI-ALPS (Diffusion Tensor Image
Analysis along the Perivascular Space) index from DSI Studio QSDR output
(tensor components + FA). It features fixed MNI-coordinate ROIs, automatic
FA scale detection, and data-quality QC warnings.

License: MIT.

![SlicerDTIALPS screenshot](https://raw.githubusercontent.com/niyaziacer/SlicerDTIALPS/main/Screenshots/Screenshot1.png)

## Data preparation (DSI Studio)

**The module does not perform reconstruction — it only reads DSI Studio's
output.** Before using this module, process your diffusion data in DSI
Studio:

1. **Step 1 — SRC creation**: DICOM (or NIfTI + `.bval`/`.bvec`) → SRC
   (the resulting file may have a `.sz` extension on Windows).
2. **Step 2 — Reconstruction**: select **QSDR** (not GQI, not DTI).
   - Template: **human, 2mm**
   - Output metrics: check **tensor** (produces `txx`, `tyy`, `tzz`), **fa**,
     and **md**
3. **Step 3 — Export**: export the `txx`, `tyy`, `tzz`, `dti_fa`, and `md`
   maps as NIfTI (`.nii.gz`). These five files are the module's inputs.

### QSDR is required

The module places its four ROIs at **fixed MNI coordinates**
(`proj_L`, `proj_R`, `assoc_L`, `assoc_R`). This is only anatomically valid
if the input volumes are already normalized to MNI/template space — which is
exactly what QSDR reconstruction does. If you instead export **native
(subject) space** data, the ROIs will fall in the wrong anatomical location
and the resulting ALPS value will be meaningless.

## Tutorial / Video

A short walkthrough showing how to obtain the tensor components (`txx`,
`tyy`, `tzz`), FA, and MD from DSI Studio — SRC creation, QSDR
reconstruction, and exporting the NIfTI files this module expects as input:

▶ [Watch on YouTube](https://www.youtube.com/watch?v=R1CVh612a6I)

## Usage

1. For each of the five inputs (txx, tyy, tzz, FA, MD), load the
   corresponding NIfTI file with the **"..."** button next to its selector.
   `txx`/`tyy`/`tzz`/`FA` are required; `MD` is optional (enables an extra
   QC check).
2. Click **Apply** — the module computes and displays:
   - Left / right / mean ALPS index
   - A per-ROI table (Dxx, Dyy, Dzz, FA, voxel count, dominant axis vs.
     expected axis)
   - QC warnings (see below)
   - Automatic ROI markups placed in the scene at the exact voxel centers
     used for the computation
3. Click **Save as CSV** to export all of the above to a CSV file. The CSV also
   records, for every input, the node name, **full file path, modification time
   and size**, so you can always tell which export a result came from.

### Checking the ROI placement: direction color map

Click **Show direction color map (QC)** to add an approximate direction-encoded
color map to the scene and show it as the background (after **Apply** the axial
slice jumps to the ROI plane):

- **R = Dxx** (left-right), **G = Dyy** (anterior-posterior),
  **B = Dzz** (superior-inferior); brightness = FA.
- Projection ROIs (**red** markups) should sit on **blue** fibers and
  association ROIs (**cyan** markups) on **green** fibers, lateral to the
  lateral-ventricle body.

> This is **not** a true DEC map. A true DEC map needs the principal
> eigenvector (the full tensor, `txy`/`txz`/`tyz` as well); the module only has
> the diagonal components. For fibers that run along the image axes (the
> projection and association fibers around the ALPS ROIs) the colors agree with
> a true DEC map, which is enough for a visual placement check. It is a QC aid
> only and is not used in the ALPS computation. The ROI check from the table
> (dominant axis = Dzz for projection, Dyy for association) is the numeric
> counterpart.

### ROI definition

Fixed MNI centers (mm): `proj_L` (-26, -16, 27), `proj_R` (26, -16, 27),
`assoc_L` (-38, -16, 27), `assoc_R` (38, -16, 27). The four ROIs are spheres
whose **radius is in real millimetres** (the distance is computed with the voxel
size). The default is **3 mm** (6 mm diameter; 19 voxels at 2 mm resolution,
before the FA mask); change it with the **ROI radius** box in the module (1-8 mm).
Only voxels with FA ≥ 0.20 are averaged. The radius used is shown in the CSV
(`ROI_Radius_mm`).

> Earlier versions documented 3 mm but actually used 2 voxels = 4 mm
> (33 voxels). Set the radius to 4 mm to reproduce those numbers.

**Which radius?** The literature has no single standard: most studies use a
5 mm *diameter* circle/sphere (2.5 mm radius), while a test-retest study
(CHAMONIX, Jpn J Radiol) used a much larger ~9.4 mm sphere because larger ROIs
gave higher reproducibility. Small ROIs are noisy; large ROIs mix in neighboring
fibers and push the ALPS value down. The absolute ALPS value therefore depends
on the ROI size - **use one radius for all subjects of a study** and do not
compare absolute values across studies with different ROI sizes.

At 2 mm resolution only a few radii differ (voxel centers are on a 2 mm grid):

| radius | voxels / ROI | note |
|---|---|---|
| 1.0-2.5 mm | 7 | centre + 6 neighbours; below the 10-voxel QC limit, the module warns |
| 3.0 mm (default) | 19 | |
| 3.5 mm | 27 | |
| 4.0 mm | 33 | former effective size |

Sensitivity example (one subject, QSDR 2 mm, mean ALPS): 2.5 mm 1.39, 3 mm 1.35,
3.5 mm 1.34, 4 mm 1.33. This is one subject - for a study, run your cohort with
2-3 radii (e.g. 3 and 4 mm) and report that the conclusion does not depend on
the choice.

## Troubleshooting / tips

*(learned from real testing)*

- **File paths**: avoid non-ASCII characters (e.g. Turkish `ü`, `ö`) and
  parentheses `( )` in folder or file names. Both DSI Studio and Slicer may
  silently fail to load such paths. Copy your data to a plain ASCII path if
  you run into unexplained load failures.
- **Check for slice gaps before reconstruction**: verify that slice spacing
  equals slice thickness (no inter-slice gap). A gap cannot be fixed later
  in DSI Studio or in this module — it makes the resulting ALPS value
  unreliable from the start.
- **Use one export for all five maps**: re-exporting a subject several times
  leaves several sets of identically named files (`..._txx.nii.gz`, ...). Mixing
  maps from different exports silently changes the result (ALPS differed by
  about 1 % between three exports of the same subject). The module now shows the
  folder and modification time of every input and warns when the inputs come
  from different folders or were written more than an hour apart.
- **Keep the protocol consistent across a cohort**: all subjects should be
  acquired with the *same* b-value, direction count, and slice geometry.
  ALPS values computed from different protocols are not directly
  comparable to each other, even if each one looks individually plausible.

## Data suitability criteria

*(derived from testing on four real subjects — see notes below)*

DTI-ALPS cannot be reliably computed from every dataset. Recommended
conditions for trustworthy results:

- **Number of directions ≥ 20** (30+ preferred)
- **Consistent b-value** (~1000 s/mm² typical). Subjects reconstructed with
  **different b-values are not comparable to each other** — a higher
  b-value lowers the measured MD, shifting the whole diffusivity scale and
  artificially inflating ALPS.
- **Slices must be contiguous — no slice gap.** When a gap exists between
  slices (slice thickness < spacing between slices), QSDR's warping to the
  template distorts diffusivity along the z-axis and inflates the ALPS
  index.
- **QSDR registration quality (R2) > 0.90**
- **White-matter MD ≈ 0.6–1.2 ×10⁻³ mm²/s** (this pipeline's own
  `md.nii.gz` scale, not raw mm²/s — see QC section)

The module checks MD and ALPS plausibility automatically and warns when
values fall outside these ranges — see below.

## Example results

*(for orientation, not validation targets — every dataset should still be
judged on its own QC output)*

- A clean b=1000 subject: ALPS ≈ 1.3, all QC checks pass.
- A b=2000 subject: ALPS may still be plausible, but an MD warning can
  appear because the diffusivity scale shifts with b-value.
- A dataset with a slice gap or noisy/washed-out FA: ALPS comes out
  inflated (>2), and QC warns — treat these results as unreliable, do not
  use them.

## QC warnings

The module does **not** silently pass bad data. After Apply, it warns if:

- Mean MD (across the 4 ROIs) is outside the 0.6–1.2 physiological range
- Mean ALPS is outside the 0.9–1.8 literature range
- A ROI's dominant diffusivity axis differs from the expected axis
  (projection ROIs should be Dzz-dominant, association ROIs Dyy-dominant)
- A ROI has fewer than 10 voxels passing the FA threshold

If none of these trigger, the module reports "All checks passed."

## References

- Taoka T, et al. "Evaluation of glymphatic system activity with the
  diffusion MR technique: diffusion tensor image analysis along the
  perivascular space (DTI-ALPS) in Alzheimer's disease cases." *Jpn J
  Radiol.* 2017.
- Barisano G, et al. / Liu X, et al. — MNI coordinates for the ALPS
  projection and association fiber ROIs.

## Development

The numeric core (`DTIALPSLogic._computeALPSCore`, `directionColor`,
`inputSpreadWarnings`) is plain NumPy and is tested without Slicer:

```
pip install -r requirements-dev.txt
python -m pytest -q
```

The Slicer user interface (the **Show direction color map** button, volume
loading) can only be exercised inside Slicer.
