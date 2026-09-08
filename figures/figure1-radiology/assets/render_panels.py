"""Render every real-image panel for the radiology pipeline figure."""
import os, glob, sys, json
import numpy as np
import pydicom
from pydicom.pixel_data_handlers.util import apply_modality_lut
import nibabel as nib
from scipy.ndimage import zoom, shift as ndshift, binary_erosion
from PIL import Image

D = "data"; OUT = "panels"
for sub in ("01_modalities", "02_preprocessing", "03_features"):
    os.makedirs(f"{OUT}/{sub}", exist_ok=True)

# ---------------------------------------------------------------- helpers
def rad(a):
    """NIfTI is RAS+ (index 0 -> patient RIGHT); flip so patient right is on the
    viewer's LEFT, i.e. radiological convention. DICOM series are already LPS and
    need no flip."""
    return np.fliplr(a)

def norm(a, lo=None, hi=None, p=(0.5, 99.5)):
    a = a.astype(np.float32)
    if lo is None: lo, hi = np.percentile(a, p)
    if hi <= lo: hi = lo + 1
    return np.clip((a - lo) / (hi - lo), 0, 1)

def win(a, level, width):
    lo, hi = level - width/2, level + width/2
    return np.clip((a - lo) / (hi - lo), 0, 1)

def png(arr, path, size=768, cmap=None, aspect=1.0, mask=None,
        mask_rgb=(232,122,63), mask_alpha=0.55, contour_only=True, filt=Image.LANCZOS):
    """arr in [0,1]. aspect = physical y/x ratio. Writes an isotropic PNG."""
    a = np.clip(arr, 0, 1)
    if cmap is None:
        rgb = np.repeat((a*255).astype(np.uint8)[..., None], 3, axis=2)
    else:
        import matplotlib
        rgb = (matplotlib.colormaps[cmap](a)[..., :3]*255).astype(np.uint8)
    if mask is not None:
        m = mask.astype(bool)
        if contour_only:
            m = m & ~binary_erosion(m, iterations=2)
        rgb[m] = ((1-mask_alpha)*rgb[m] + mask_alpha*np.array(mask_rgb)).astype(np.uint8)
    im = Image.fromarray(rgb)
    h, w = a.shape
    ph = int(round(h*aspect))
    im = im.resize((w, ph), filt)
    s = size/max(w, ph)
    im = im.resize((max(1,int(w*s)), max(1,int(ph*s))), filt)
    im.save(path)
    print("   ", path, im.size)

def load_dicom_series(folder, modality=None):
    files = [f for f in glob.glob(f"{folder}/**/*", recursive=True) if os.path.isfile(f)]
    ds = []
    for f in files:
        try:
            d = pydicom.dcmread(f, force=True)
            if not hasattr(d, "PixelData"): continue
            if modality and getattr(d, "Modality", None) != modality: continue
            ds.append(d)
        except Exception: pass
    if not ds: raise RuntimeError(f"no DICOM in {folder}")
    def z(d):
        try: return float(d.ImagePositionPatient[2])
        except Exception: return float(getattr(d, "InstanceNumber", 0))
    ds.sort(key=z)
    vol = np.stack([apply_modality_lut(d.pixel_array, d).astype(np.float32) for d in ds])
    ps = [float(x) for x in ds[0].PixelSpacing]
    try: st = abs(z(ds[1]) - z(ds[0]))
    except Exception: st = float(getattr(ds[0], "SliceThickness", 1))
    return vol, ds, (st, ps[0], ps[1])   # vol[z,y,x], spacing (z,y,x)

def suv_factor(d):
    try:
        w = float(d.PatientWeight)*1000
        r = d.RadiopharmaceuticalInformationSequence[0]
        dose = float(r.RadionuclideTotalDose)
        half = float(r.RadionuclideHalfLife)
        t0 = r.RadiopharmaceuticalStartTime; t1 = d.SeriesTime
        def sec(t): t=str(t); return int(t[:2])*3600+int(t[2:4])*60+float(t[4:])
        dt = sec(t1)-sec(t0)
        return w/(dose*0.5**(dt/half))
    except Exception:
        return None

# ================================================================ 1. MODALITIES
print("[1] modality panels")

# --- chest radiograph (CC0)
cx = np.array(Image.open("data/cxr/cxr_pa.jpg").convert("L")).astype(np.float32)
png(norm(cx, p=(1, 99.7)), f"{OUT}/01_modalities/xray_chest_pa.png", size=900)

# --- mammography (CMMD, CC BY 4.0)
mg_files = sorted(f for f in glob.glob("data/cmmd/MG/**/*", recursive=True) if os.path.isfile(f))
for i, f in enumerate(mg_files[:2]):
    d = pydicom.dcmread(f, force=True)
    a = d.pixel_array.astype(np.float32)
    if getattr(d, "PhotometricInterpretation", "") == "MONOCHROME1": a = a.max()-a
    view = str(getattr(d, "ViewPosition", "") or "")
    if not view:
        try: view = str(d.ViewCodeSequence[0].CodeMeaning).replace(" ", "-")
        except Exception: view = f"view{i}"
    lat = str(getattr(d, "ImageLaterality", "") or "")
    png(norm(a, p=(2, 99.9)), f"{OUT}/01_modalities/mammo_{lat}_{view}.png", size=900)
    print(f"      (laterality={lat!r} view={view!r})")

# --- ultrasound (B-mode liver, CC BY 4.0)
us_files = sorted(f for f in glob.glob("data/us/US/**/*", recursive=True) if os.path.isfile(f))
d = pydicom.dcmread(us_files[0], force=True)
a = d.pixel_array
if a.ndim == 4: a = a[a.shape[0]//2]
if a.ndim == 3 and a.shape[-1] == 3: a = a[..., 0]
# DICOM US declares the actual image region; everything else is vendor UI chrome
try:
    r0 = d.SequenceOfUltrasoundRegions[0]
    x0u, x1u = int(r0.RegionLocationMinX0), int(r0.RegionLocationMaxX1)
    y0u, y1u = int(r0.RegionLocationMinY0), int(r0.RegionLocationMaxY1)
    print(f"      US region x[{x0u}:{x1u}] y[{y0u}:{y1u}] of {a.shape}")
    a = a[y0u:y1u, x0u:x1u]
except Exception as e:
    print("      (no ultrasound region tag:", e, ")")
png(norm(a.astype(np.float32), p=(0, 99.8)), f"{OUT}/01_modalities/ultrasound_liver.png", size=800)

# --- CT + PET (autoPET, CC BY 4.0)
ct, ct_ds, ct_sp = load_dicom_series("data/autopet2/CT", "CT")
pt, pt_ds, pt_sp = load_dicom_series("data/autopet2/PT", "PT")
print(f"    CT {ct.shape} sp={tuple(round(x,2) for x in ct_sp)}  "
      f"PET {pt.shape} sp={tuple(round(x,2) for x in pt_sp)}")
sf = suv_factor(pt_ds[0])
pet = pt*sf if sf else pt
print("    SUV factor:", round(sf, 6) if sf else "n/a (raw counts)")

k = ct.shape[0]//2
png(win(ct[k], 40, 400), f"{OUT}/01_modalities/ct_axial_softtissue.png")
png(win(ct[:, ct.shape[1]//2, :][::-1], 40, 500),
    f"{OUT}/01_modalities/ct_coronal.png", aspect=ct_sp[0]/ct_sp[2], size=900)

# whole-body PET MIP -- the canonical PET picture
mip_cor = pet.max(axis=1)[::-1]
SUV_MAX = 5.0   # standard clinical PET MIP display window, SUVbw 0-5

np.save("/tmp/_ct.npy", ct); np.save("/tmp/_pet.npy", pet)
json.dump({"ct_sp": list(ct_sp), "pt_sp": list(pt_sp)}, open("/tmp/_sp.json","w"))

# --- MRI (AMOS22, CC BY 4.0)
mr = nib.as_closest_canonical(nib.load("data/amos/amos22/imagesTr/amos_0588.nii.gz"))
mrd = mr.get_fdata(); mrz = mr.header.get_zooms()[:3]
png(norm(rad(np.rot90(mrd[:, :, mrd.shape[2]//2])), p=(1, 99.5)),
    f"{OUT}/01_modalities/mri_axial.png")
png(norm(rad(np.rot90(mrd[:, mrd.shape[1]//2, :])), p=(1, 99.5)),
    f"{OUT}/01_modalities/mri_coronal.png", aspect=mrz[1]/mrz[0], size=900)
print("done modalities\n")

# ---- fix 1: crop PET MIP to the body, not the 82 cm scanner FOV
def bbox_cols(a, thr):
    c = a.max(axis=0); idx = np.where(c > thr)[0]
    return (idx.min(), idx.max()) if len(idx) else (0, a.shape[1]-1)
thr = np.percentile(mip_cor, 99.0)
c0, c1 = bbox_cols(mip_cor, thr)
pad = 25
c0, c1 = max(0, c0-pad), min(mip_cor.shape[1], c1+pad)
png(1-np.clip(mip_cor[:, c0:c1]/SUV_MAX, 0, 1),
    f"{OUT}/01_modalities/pet_mip_coronal.png", aspect=pt_sp[0]/pt_sp[2], size=1000)

# ---- fix 2: use the axial-acquired MRI for the modality panel
mr2 = nib.as_closest_canonical(nib.load("data/amos/amos22/imagesTr/amos_0584.nii.gz"))
m2 = mr2.get_fdata(); z2 = mr2.header.get_zooms()[:3]
print(f"    MRI(0584) {m2.shape} sp={tuple(round(float(x),2) for x in z2)}")
png(norm(rad(np.rot90(m2[:, :, m2.shape[2]//2])), p=(1, 99.5)),
    f"{OUT}/01_modalities/mri_axial.png", aspect=z2[1]/z2[0])
png(norm(rad(np.rot90(m2[:, m2.shape[1]//2, :])), p=(1, 99.5)),
    f"{OUT}/01_modalities/mri_coronal.png", aspect=z2[2]/z2[0], size=900)

# ================================================================ 2. PREPROCESSING
print("\n[2] preprocessing panels")
P = f"{OUT}/02_preprocessing"

# --- 2a WINDOWING: one CT slice, four settings
# pick the slice with the most aerated lung so that lung/soft-tissue/bone windows
# genuinely differ; an abdominal slice makes the lung window meaningless
from scipy.ndimage import binary_fill_holes
# fill per 2D slice: in 3D the lungs drain to room air through the trachea and so are
# never enclosed, which would leave them outside the body mask.
air = np.array([((ct[i] < -700) & binary_fill_holes(ct[i] > -400)).sum()
                for i in range(ct.shape[0])])
kk = int(np.argmax(air))
print(f"    windowing slice z={kk} ({air[kk]} aerated-lung voxels inside the body)")
sl = ct[kk]
png(norm(sl, lo=sl.min(), hi=sl.max()), f"{P}/a_window_none_fullrange.png")
for nm, (lv, wd) in {"lung": (-600, 1500), "softtissue": (40, 400),
                     "bone": (400, 1800), "mediastinum": (50, 350)}.items():
    png(win(sl, lv, wd), f"{P}/a_window_{nm}.png")

# --- 2b INTENSITY STANDARDIZATION: two MRIs, raw scales vs z-scored
raws = []
_v588 = nib.as_closest_canonical(nib.load("data/amos/amos22/imagesTr/amos_0588.nii.gz"))
for tag, v, zz in (("scan_A", m2, z2), ("scan_B", _v588.get_fdata(), _v588.header.get_zooms()[:3])):
    s = rad(np.rot90(v[:, :, v.shape[2]//2]))
    raws.append((tag, s, float(zz[0])/float(zz[1])))
    print(f"    MRI {tag}: raw range {s.min():.0f}-{s.max():.0f}, mean {s.mean():.0f}")
gmax = max(s.max() for _, s, _ in raws)
for tag, s, ar in raws:                  # same global scale -> the two look different
    png(np.clip(s/gmax, 0, 1), f"{P}/b_intensity_raw_{tag}.png", aspect=ar)
for tag, s, ar in raws:                  # z-score inside the body -> comparable
    body = s > np.percentile(s, 55)
    z = (s - s[body].mean())/s[body].std()
    png(np.clip((z+2)/6, 0, 1), f"{P}/b_intensity_zscored_{tag}.png", aspect=ar)

# --- 2c RESAMPLING: genuinely anisotropic MRI, native vs 1 mm isotropic
cor = rad(np.rot90(m2[:, m2.shape[1]//2, :]))
png(norm(cor, p=(1, 99.5)), f"{P}/c_spacing_native_1.39x3.0mm.png",
    aspect=float(z2[2])/float(z2[0]), size=700, filt=Image.NEAREST)
iso = zoom(m2, (float(z2[0]), float(z2[1]), float(z2[2])), order=1)
cor_iso = rad(np.rot90(iso[:, iso.shape[1]//2, :]))
png(norm(cor_iso, p=(1, 99.5)), f"{P}/c_spacing_isotropic_1mm.png", aspect=1.0, size=700)
print(f"    native {m2.shape} @ {tuple(round(float(x),2) for x in z2)} -> isotropic {iso.shape} @ 1mm")

# --- 2d ORIENTATION / 2.5D: three canonical planes from one CT
png(win(ct[kk], 40, 400), f"{P}/d_plane_axial.png", size=600)
png(win(ct[:, ct.shape[1]//2, :][::-1], 40, 400), f"{P}/d_plane_coronal.png",
    aspect=ct_sp[0]/ct_sp[2], size=600)
png(win(ct[:, :, ct.shape[2]//2][::-1], 40, 400), f"{P}/d_plane_sagittal.png",
    aspect=ct_sp[0]/ct_sp[1], size=600)

# --- 2e MIP: single slice vs slab, lung window
lo, hi = kk-12, kk+12
png(win(ct[kk], -600, 1500), f"{P}/e_mip_single_slice.png")
png(win(ct[lo:hi].max(axis=0), -600, 1500), f"{P}/e_mip_slab_60mm.png")

# --- 2f REGISTRATION: real PET/CT pair (hardware co-registered) + simulated offset
print("    registration (PET/CT)")
import json as _json
zc = ct.shape[0]
# resample PET onto the CT grid (nearest in z, linear in-plane)
fac = (ct.shape[0]/pet.shape[0], ct.shape[1]/pet.shape[1], ct.shape[2]/pet.shape[2])
pet_on_ct = zoom(pet, fac, order=1)
cj = ct.shape[1]//2
ct_cor  = ct[:, cj, :][::-1]
pet_cor = pet_on_ct[:, cj, :][::-1]
asp = ct_sp[0]/ct_sp[2]

def fuse(gray01, hot01, alpha=0.55):
    import matplotlib
    base = np.repeat(gray01[..., None], 3, axis=2)
    hot  = matplotlib.colormaps["hot"](hot01)[..., :3]
    w = (hot01[..., None]**0.7)*alpha
    return np.clip(base*(1-w) + hot*w, 0, 1)

g = win(ct_cor, 40, 500)
h = norm(pet_cor, p=(60, 99.7))
Image.fromarray((fuse(g, h)*255).astype(np.uint8)).resize(
    (int(700), int(700*g.shape[0]*asp/g.shape[1])), Image.LANCZOS
).save(f"{P}/f_registration_AFTER_fused.png")
png(g, f"{P}/f_registration_moving_CT.png", aspect=asp, size=700)
png(1-h, f"{P}/f_registration_fixed_PET.png", aspect=asp, size=700)
# simulated misalignment: known rigid offset applied to the PET
off = ndshift(pet_on_ct, (26, 0, 30), order=1, mode="nearest")[:, cj, :][::-1]
hb = norm(off, p=(60, 99.7))
Image.fromarray((fuse(g, hb)*255).astype(np.uint8)).resize(
    (int(700), int(700*g.shape[0]*asp/g.shape[1])), Image.LANCZOS
).save(f"{P}/f_registration_BEFORE_simulated_offset.png")
# checkerboard, the standard registration QC view
def checker(a, b, n=12):
    out = a.copy(); s0, s1 = a.shape[0]//n, a.shape[1]//n
    for i in range(n+1):
        for j in range(n+1):
            if (i+j) % 2: out[i*s0:(i+1)*s0, j*s1:(j+1)*s1] = b[i*s0:(i+1)*s0, j*s1:(j+1)*s1]
    return out
# PET/CT checkerboards read poorly (the two modalities look nothing alike), so the
# canonical CT-vs-CT checkerboard is used to show what mis-registration looks like.
g_shift = win(ndshift(ct, (0, 0, 22), order=1, mode="nearest")[:, cj, :][::-1], 40, 500)
png(checker(g, g_shift), f"{P}/f_registration_checkerboard_BEFORE_ctct.png", aspect=asp, size=700)
png(checker(g, g),       f"{P}/f_registration_checkerboard_AFTER_ctct.png",  aspect=asp, size=700)
png(checker(g, 1-h),  f"{P}/f_registration_checkerboard_petct_after.png",  aspect=asp, size=700)
png(checker(g, 1-hb), f"{P}/f_registration_checkerboard_petct_before.png", aspect=asp, size=700)

# --- 2g SEGMENTATION: TotalSegmentator organ masks + autoPET tumour mask
print("    segmentation")
tsc = nib.as_closest_canonical(nib.load("data/totalseg/s0011/ct.nii.gz"))
tv = tsc.get_fdata()
ORG = ["liver","spleen","heart","aorta","lung_upper_lobe_left","lung_lower_lobe_right","vertebrae_T8"]
lab = np.zeros(tv.shape, np.uint8)
for i, o in enumerate(ORG, 1):
    m = nib.as_closest_canonical(nib.load(f"data/totalseg/s0011/segmentations/{o}.nii.gz")).get_fdata()
    lab[m > .5] = i
kz = int(np.argmax((lab > 0).sum(axis=(0, 1))))
base = rad(win(np.rot90(tv[:, :, kz]), 40, 400))
lsl = rad(np.rot90(lab[:, :, kz]))
png(base, f"{P}/g_seg_input_ct.png", size=700)
import matplotlib as _mpl
pal = (_mpl.colormaps["tab10"](np.arange(len(ORG)) % 10)[:, :3]*255).astype(np.uint8)
rgb = np.repeat((base*255).astype(np.uint8)[..., None], 3, axis=2)
edge = np.zeros_like(lsl, bool)
for i in range(1, len(ORG)+1):
    m = lsl == i
    if not m.any(): continue
    e = m & ~binary_erosion(m, iterations=2)
    rgb[m] = (0.72*rgb[m] + 0.28*pal[i-1]).astype(np.uint8)
    rgb[e] = pal[i-1]
Image.fromarray(rgb).resize((700, 700), Image.LANCZOS).save(f"{P}/g_seg_organs_overlay.png")
png((lsl > 0).astype(float), f"{P}/g_seg_mask_binary.png", size=700)

# autoPET tumour segmentation: lesion overlay + detection box, real annotations
segf = sorted(f for f in glob.glob("data/autopet2/SEG/**/*.dcm", recursive=True) if os.path.isfile(f))
sd = pydicom.dcmread(segf[0], force=True)
if not hasattr(sd, "file_meta") or "TransferSyntaxUID" not in sd.file_meta:
    from pydicom.uid import ImplicitVRLittleEndian
    from pydicom.dataset import FileMetaDataset
    if not hasattr(sd, "file_meta"): sd.file_meta = FileMetaDataset()
    sd.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
sm = sd.pixel_array.astype(bool)
print(f"    autoPET SEG {sm.shape}, tumour voxels {int(sm.sum())}")
# SEG frames are in the PET frame order but stored inferior->superior; match PET z
if sm.shape[0] == pet.shape[0]:
    # verified against SEG PerFrameFunctionalGroupsSequence: frame z runs ascending,
    # the same order as the z-sorted PET series, so no flip.
    seg = sm
else:
    seg = zoom(sm.astype(float), (pet.shape[0]/sm.shape[0], pet.shape[1]/sm.shape[1],
                                  pet.shape[2]/sm.shape[2]), order=0) > .5
# pick the axial slice with the largest lesion cross-section
kt = int(np.argmax(seg.reshape(seg.shape[0], -1).sum(1)))
print(f"    peak lesion slice z={kt}, {int(seg[kt].sum())} px")
petsl = norm(pet[kt], p=(50, 99.8))
png(1-petsl, f"{P}/h_lesion_pet_axial.png", size=700)
png(1-petsl, f"{P}/h_lesion_pet_axial_seg.png", size=700, mask=seg[kt],
    mask_rgb=(214, 60, 60), mask_alpha=0.95)
# same lesion on the CT, and on the fused image
ctk = int(round(kt*ct.shape[0]/pet.shape[0]))
ctk = min(max(ctk, 0), ct.shape[0]-1)
segct = zoom(seg[kt].astype(float), (ct.shape[1]/seg.shape[1], ct.shape[2]/seg.shape[2]), order=0) > .5
png(win(ct[ctk], 40, 400), f"{P}/h_lesion_ct_axial.png", size=700)
png(win(ct[ctk], 40, 400), f"{P}/h_lesion_ct_axial_seg.png", size=700, mask=segct,
    mask_rgb=(214, 60, 60), mask_alpha=0.95)
# detection view: axis-aligned box around the lesion, drawn on the fused slice
pet_k = zoom(pet[kt].astype(float), (ct.shape[1]/pet.shape[1], ct.shape[2]/pet.shape[2]), order=1)
fus = fuse(win(ct[ctk], 40, 500), norm(pet_k, p=(60, 99.7)))
rgb = (fus*255).astype(np.uint8)
ys, xs = np.where(segct)
if len(ys):
    pad = 14
    y0b, y1b = max(0, ys.min()-pad), min(rgb.shape[0]-1, ys.max()+pad)
    x0b, x1b = max(0, xs.min()-pad), min(rgb.shape[1]-1, xs.max()+pad)
    for t in range(3):
        rgb[y0b+t, x0b:x1b] = (255, 210, 60); rgb[y1b-t, x0b:x1b] = (255, 210, 60)
        rgb[y0b:y1b, x0b+t] = (255, 210, 60); rgb[y0b:y1b, x1b-t] = (255, 210, 60)
Image.fromarray(rgb).resize((700, 700), Image.LANCZOS).save(f"{P}/h_lesion_detection_box_fused.png")
print("     ", f"{P}/h_lesion_detection_box_fused.png")
# whole-body PET MIP with the lesion burden projected on it
mipl = seg.max(axis=1)[::-1]
mipp = 1-np.clip(pet.max(axis=1)[::-1]/SUV_MAX, 0, 1)
c0m, c1m = bbox_cols(pet.max(axis=1)[::-1], np.percentile(pet.max(axis=1), 99.0))
c0m, c1m = max(0, c0m-25), min(mipp.shape[1], c1m+25)
png(mipp[:, c0m:c1m], f"{P}/h_lesion_pet_mip_seg.png", aspect=pt_sp[0]/pt_sp[2], size=1000,
    mask=mipl[:, c0m:c1m], mask_rgb=(214, 60, 60), mask_alpha=0.95, contour_only=False)

# ================================================================ 3. FEATURES
print("\n[3] radiomic feature panels")
F = f"{OUT}/03_features"
liver = nib.as_closest_canonical(nib.load("data/totalseg/s0011/segmentations/liver.nii.gz")).get_fdata()
kl = int(np.argmax(liver.sum(axis=(0, 1))))
lm = rad(np.rot90(liver[:, :, kl])) > .5
ctl = rad(np.rot90(tv[:, :, kl]))
ys, xs = np.where(lm)
y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
roi = ctl[y0:y1, x0:x1]; roim = lm[y0:y1, x0:x1]
png(win(roi, 60, 250), f"{F}/roi_liver_crop.png", size=520)
png(win(roi, 60, 250), f"{F}/roi_liver_crop_masked.png", size=520, mask=roim,
    mask_rgb=(232,122,63), mask_alpha=0.9)

# GLCM computed from the real ROI
q = np.clip(((win(roi, 60, 250)*31).astype(int)), 0, 31)
glcm = np.zeros((32, 32), float)
a1, a2 = q[:, :-1][roim[:, :-1]], q[:, 1:][roim[:, :-1]]
np.add.at(glcm, (a1.ravel(), a2.ravel()), 1)
glcm = (glcm + glcm.T); glcm /= glcm.sum()
png(norm(np.log1p(glcm*1e3)), f"{F}/glcm_matrix_32bin.png", size=420, cmap="magma")

# intensity histogram of the same ROI
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
vals = roi[roim]
fig = plt.figure(figsize=(3.2, 2.0), dpi=300)
ax = fig.add_axes([0.02, 0.04, 0.96, 0.92])
ax.hist(vals, bins=48, range=(-50, 180), color="#16506e", edgecolor="none")
for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
ax.set_yticks([]); ax.tick_params(labelsize=6, length=2, colors="#555")
fig.savefig(f"{F}/histogram_liver_roi.png", transparent=True)
plt.close(fig)
print(f"    liver ROI: {int(roim.sum())} px, HU mean {vals.mean():.0f} sd {vals.std():.0f}")
print("     ", f"{F}/histogram_liver_roi.png")

n = sum(len(fs) for _, _, fs in os.walk(OUT))
print(f"\nDONE: {n} panels under {OUT}/")
