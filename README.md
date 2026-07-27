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
3. Click **"CSV olarak kaydet"** to export all of the above to a CSV file.

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
