"""Build the radiology row of CCR Figure 1 in the project's "Ink" style.

The figure is a four-column pipeline schematic: input data, preprocessing,
models, clinical tasks. It is a remake of the 31 Aug 2026 HTML build (the Inter
face and cream chips) under the project's style guide, ``ink_style_guide.md``,
and the operational rules in ``AGENTS.md`` beside it.

What changed from the original, and why, is recorded in ``docs/DECISIONS.md``.
The short version: IBM Plex Serif and Sans instead of Inter; every hue is one of
the project's fixed modality hues or a neutral, so the cream chips became white
cards and the coloured overlays in the image panels were snapped to the
palette; explanatory sentences moved from the artwork to the legend; the panel
carries a serif letter and title; the type ladder is anchored at 5.5 pt for a
7.5 in wide figure. The frame, the four dashed column boxes, the header row,
the strips, chips, captions, dashed link, and credit lines keep the original's
geometry, scaled from its 1400 px canvas.

Command line::

    conda activate ccrfig
    python build.py --output figures/

Style comes from the collaborator's clone. ``from trends.plotting import style``
registers the vendored IBM Plex faces at import and raises if any is missing or
substituted. Do not catch that error.

Panels are the real, openly licensed images rendered by
``assets/render_panels.py``; this script only crops,
resizes, and recolours them. Icons are the 37 hand-authored SVGs in
``assets/icons`` plus two of the project's approved icons.
"""

from __future__ import annotations

import argparse
import io
import re
from dataclasses import dataclass
from pathlib import Path

import cairosvg
import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.textpath import TextPath  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402
from trends.plotting import style  # noqa: E402

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
PANELS = ASSETS / "panels"
ICONS = ASSETS / "icons"


def _project_icons() -> Path:
    """Locate the project's approved icon set.

    This figure is built in two places: the working repository, where the
    collaborator's repository sits beside it as a clone, and the collaborator's
    repository itself, where the icons are one level up. Try both so a single
    build.py serves both homes.
    """
    candidates = (
        HERE.parent / "icons",                                            # inside figures/
        HERE.parent.parent / "ccr-ai-rads-path-review-2026" / "figures" / "icons",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "approved icon set not found; looked in "
        + ", ".join(str(c) for c in candidates)
    )


#: The project's approved icon set (see figures/AGENTS.md, "Icons").
PROJECT_ICONS = _project_icons()

OUTPUT_STEM = "figure1_radiology"

# --------------------------------------------------------------------------
# Geometry, in inches, measured from the top-left corner of the page.
#
# The layout is the original's, scaled: a 1400 px canvas becomes 7.5 in, so
# one original pixel is K = 7.5/1400 in. Every box below is the original's
# box at that scale: the section title above the frame, the frame with its
# padding, the header row, the four dashed column boxes 580 px tall with
# column widths 239/518/353/173 and 16 px gaps, the 44 px bottom padding that
# holds the dashed link, and the credit lines under the frame. The page is
# 7.5 by 4.33 in, aspect 1.73, against the original PDF page's 1.74.
#
# One deliberate departure: 0.16 in moved from the preprocessing column to the
# clinical-tasks column (518/173 px became 489/202), because the task labels
# at the 6 pt the type ladder requires do not fit 173 px at this scale. The
# other three columns keep their widths to 0.01 in.
# --------------------------------------------------------------------------
K = 7.5 / 1400.0
W_IN = 7.5
TOP = 16 * K                          # canvas padding above the section title
TITLE_ROW = 33 * K                    # "A  Radiology" row
FRAME_X = 18 * K
FRAME_W = 1364 * K
FRAME_TOP = TOP + TITLE_ROW
FRAME_PAD_T, FRAME_PAD_S, FRAME_PAD_B = 14 * K, 17 * K, 44 * K
HEAD_ROW = 40 * K                     # column titles and the care-pathway note (35 px in the original)
BOX_TOP = FRAME_TOP + FRAME_PAD_T + HEAD_ROW
BOX_H = 580 * K
BOX_PAD_Y, BOX_PAD_X = 11 * K, 9 * K
COL_GAP = 16 * K
COL_W = (239 * K, 489 * K, 353 * K, 202 * K)
COL_X = tuple(FRAME_X + FRAME_PAD_S + sum(COL_W[:i]) + i * COL_GAP for i in range(4))
FRAME_BOTTOM = BOX_TOP + BOX_H + FRAME_PAD_B
CREDIT_TOP = FRAME_BOTTOM + 9 * K
FS_CREDIT = 5.5
# H_IN is set below CREDIT_LINES, once the credit text has been wrapped.
CONTENT_Y0 = BOX_TOP + BOX_PAD_Y
CONTENT_H = BOX_H - 2 * BOX_PAD_Y

#: Raster resolution for embedded panels, pixels per inch of print size.
PANEL_PPI = 600
#: Raster resolution for icons, pixels per icon regardless of print size.
ICON_PX = 600

# --------------------------------------------------------------------------
# Type. The style module's ladder is for a 7.5 in figure; these sizes sit on
# its rungs. Nothing is below 5.5 pt.
# --------------------------------------------------------------------------
FS_LETTER = style.FS_PANEL_LETTER          # 12.6, serif bold
FS_TITLE = 10.3                            # guide's 18/22 of the letter, serif bold
FS_SUBTITLE = style.FS_THEME_TITLE         # 8.6, serif bold: column subtitles
FS_BLOCK = 7.0                             # block titles, sans bold
FS_CARD = 6.8                              # card primary label, sans bold
FS_MOD_LABEL = 6.0                         # modality card label: "Mammography" must fit 0.48 in
FS_CARD_SUB = 5.6                          # card secondary line, deep hue or subtle
FS_CAPTION = 5.6                           # captions under thumbnails, subtle
FS_ICON_LABEL = style.FS_NOTE              # 5.8, labels under icons
FS_TASK = 5.8                              # clinical task labels, two lines in a 0.204 in row
FS_BADGE = 5.8                             # number inside a badge

#: Deep variants for small type, from the guide's modality table.
CLINICAL_TEXT_DEEP = "#006B4E"
MOLECULAR_DEEP = "#9C6C00"

# Strokes, in points. The guide's 1.0 to 1.6 units on its canvas scale to
# 0.4 to 0.65 pt here; 0.4 pt is the floor used for hairlines.
LW_PANEL = 0.55
LW_CARD = 0.6
LW_NEUTRAL = 0.45
LW_STRUCTURAL = 0.65
LW_HAIR = 0.4
LW_ARROW = 0.65

# --------------------------------------------------------------------------
# Panel slots: key -> (file, fit, crop, recolour). ``fit`` is "cover" (crop
# to fill) or "contain" (pad with white). ``crop`` is a fractional
# left, top, right, bottom box applied first. ``recolour`` names a treatment
# below that brings a coloured overlay onto the palette.
# --------------------------------------------------------------------------
SLOTS: dict[str, tuple[str, str, tuple | None, str | None]] = {
    "mod_xray": ("01_modalities/xray_chest_pa.png", "cover", None, None),
    "mod_mammo": ("01_modalities/mammo_L_medio-lateral-oblique.png", "cover", (0.0, 0.0, 0.52, 1.0), None),
    "mod_us": ("01_modalities/ultrasound_liver.png", "cover", None, None),
    "mod_ct": ("01_modalities/ct_axial_softtissue.png", "cover", None, None),
    "mod_mri": ("01_modalities/mri_axial.png", "cover", None, None),
    "mod_pet": ("01_modalities/pet_mip_coronal.png", "contain", None, None),
    "w_full": ("02_preprocessing/a_window_none_fullrange.png", "cover", None, None),
    "w_lung": ("02_preprocessing/a_window_lung.png", "cover", None, None),
    "w_medi": ("02_preprocessing/a_window_mediastinum.png", "cover", None, None),
    "mr_raw": ("02_preprocessing/b_intensity_raw_scan_A.png", "cover", None, None),
    "mr_z": ("02_preprocessing/b_intensity_zscored_scan_A.png", "cover", None, None),
    "sp_native": ("02_preprocessing/c_spacing_native_1.39x3.0mm.png", "cover", None, None),
    "sp_iso": ("02_preprocessing/c_spacing_isotropic_1mm.png", "cover", None, None),
    "pl_ax": ("02_preprocessing/d_plane_axial.png", "cover", None, None),
    "pl_cor": ("02_preprocessing/d_plane_coronal.png", "cover", None, None),
    "pl_sag": ("02_preprocessing/d_plane_sagittal.png", "cover", None, None),
    "mip_1": ("02_preprocessing/e_mip_single_slice.png", "cover", None, None),
    "mip_60": ("02_preprocessing/e_mip_slab_60mm.png", "cover", None, None),
    "reg_before": ("02_preprocessing/f_registration_checkerboard_BEFORE_ctct.png", "cover", None, None),
    "reg_after": ("02_preprocessing/f_registration_checkerboard_AFTER_ctct.png", "cover", None, None),
    "reg_fused": ("02_preprocessing/f_registration_AFTER_fused.png", "cover", None, "pet_orange"),
    "seg_in": ("02_preprocessing/g_seg_input_ct.png", "cover", None, None),
    "seg_ov": ("02_preprocessing/g_seg_organs_overlay.png", "cover", None, "overlay_blue"),
    "seg_mask": ("02_preprocessing/g_seg_mask_binary.png", "cover", None, None),
    "roi": ("03_features/roi_liver_crop_masked.png", "cover", None, "contour_blue"),
    "hist": ("03_features/histogram_liver_roi.png", "contain", None, "bars_grey"),
    "glcm": ("03_features/glcm_matrix_32bin.png", "cover", None, "greyscale"),
    "t_screen": ("01_modalities/mammo_L_medio-lateral-oblique.png", "cover", (0.0, 0.05, 0.46, 0.75), None),
    "t_detect": ("02_preprocessing/h_lesion_ct_axial_seg.png", "cover", (0.2, 0.2, 0.8, 0.8), "contour_blue"),
    "t_seg": ("02_preprocessing/g_seg_organs_overlay.png", "cover", None, "overlay_blue"),
    "t_resp": ("02_preprocessing/h_lesion_pet_mip_seg.png", "contain", None, "lesion_orange"),
}

#: Source and licence of every panel file, for the summary and the legend.
SOURCES = {
    "01_modalities/xray_chest_pa.png": ("Wikimedia Commons, Mikael Haggstrom", "CC0"),
    "01_modalities/mammo_L_medio-lateral-oblique.png": ("CMMD, TCIA doi:10.7937/tcia.eqde-4b16", "CC BY 4.0"),
    "01_modalities/ultrasound_liver.png": ("B-mode-and-CEUS-Liver, TCIA doi:10.7937/TCIA.2021.v4z7-tc39", "CC BY 4.0"),
    "01_modalities/ct_axial_softtissue.png": ("FDG-PET-CT-Lesions v2, TCIA doi:10.7937/gkr0-xv29", "CC BY 4.0"),
    "01_modalities/mri_axial.png": ("AMOS22, Zenodo 7262581", "CC BY 4.0"),
    "01_modalities/pet_mip_coronal.png": ("FDG-PET-CT-Lesions v2, TCIA doi:10.7937/gkr0-xv29", "CC BY 4.0"),
    "02_preprocessing/a_window_none_fullrange.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/a_window_lung.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/a_window_mediastinum.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/b_intensity_raw_scan_A.png": ("AMOS22, Zenodo 7262581", "CC BY 4.0"),
    "02_preprocessing/b_intensity_zscored_scan_A.png": ("AMOS22, Zenodo 7262581", "CC BY 4.0"),
    "02_preprocessing/c_spacing_native_1.39x3.0mm.png": ("AMOS22, Zenodo 7262581", "CC BY 4.0"),
    "02_preprocessing/c_spacing_isotropic_1mm.png": ("AMOS22, Zenodo 7262581", "CC BY 4.0"),
    "02_preprocessing/d_plane_axial.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/d_plane_coronal.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/d_plane_sagittal.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/e_mip_single_slice.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/e_mip_slab_60mm.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/f_registration_checkerboard_BEFORE_ctct.png": ("FDG-PET-CT-Lesions v2, TCIA doi:10.7937/gkr0-xv29", "CC BY 4.0"),
    "02_preprocessing/f_registration_checkerboard_AFTER_ctct.png": ("FDG-PET-CT-Lesions v2, TCIA doi:10.7937/gkr0-xv29", "CC BY 4.0"),
    "02_preprocessing/f_registration_AFTER_fused.png": ("FDG-PET-CT-Lesions v2, TCIA doi:10.7937/gkr0-xv29", "CC BY 4.0"),
    "02_preprocessing/g_seg_input_ct.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/g_seg_organs_overlay.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/g_seg_mask_binary.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "02_preprocessing/h_lesion_ct_axial_seg.png": ("FDG-PET-CT-Lesions v2, TCIA doi:10.7937/gkr0-xv29", "CC BY 4.0"),
    "02_preprocessing/h_lesion_pet_mip_seg.png": ("FDG-PET-CT-Lesions v2, TCIA doi:10.7937/gkr0-xv29", "CC BY 4.0"),
    "03_features/roi_liver_crop_masked.png": ("TotalSegmentator, Zenodo 10047292", "CC BY 4.0"),
    "03_features/histogram_liver_roi.png": ("computed from the TotalSegmentator liver VOI", "CC BY 4.0"),
    "03_features/glcm_matrix_32bin.png": ("computed from the TotalSegmentator liver VOI", "CC BY 4.0"),
}


# --------------------------------------------------------------------------
# Recolouring. Colour in the panels is allowed only where it is one of the
# project's fixed hues: radiology blue for anything derived from a radiology
# image (contours, segmentation overlays), molecular orange for PET signal,
# neutral grey for bars and heat maps.
# --------------------------------------------------------------------------

def _hex_to_hue_sat(hex_colour: str) -> tuple[float, float]:
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return 0.0, 0.0
    if mx == r:
        h = (60 * ((g - b) / d) + 360) % 360
    elif mx == g:
        h = 60 * ((b - r) / d) + 120
    else:
        h = 60 * ((r - g) / d) + 240
    return h, d / mx


def snap_hues(im: Image.Image, target_hex: str, hue_lo: float = 0.0, hue_hi: float = 360.0,
              s_min: float = 0.22, v_min: float = 0.10, sat_floor: float = 0.0) -> Image.Image:
    """Replace the hue of every saturated pixel in a hue range with one palette hue.

    Value (brightness) is kept, so a colormap ramp stays a ramp and a shaded
    overlay stays shaded; saturation is kept but raised to ``sat_floor``.
    """
    hsv = np.asarray(im.convert("RGB").convert("HSV")).astype(np.float32)
    hue = hsv[..., 0] * 360.0 / 255.0
    sat = hsv[..., 1] / 255.0
    val = hsv[..., 2] / 255.0
    in_range = (hue >= hue_lo) & (hue <= hue_hi) if hue_lo <= hue_hi else (hue >= hue_lo) | (hue <= hue_hi)
    sel = (sat > s_min) & (val > v_min) & in_range
    th, ts = _hex_to_hue_sat(target_hex)
    hue[sel] = th
    sat[sel] = np.maximum(sat[sel], sat_floor) if sat_floor else sat[sel]
    if ts:
        sat[sel] = np.minimum(1.0, sat[sel] * (ts / max(ts, 1e-6)))
    out = np.stack([hue * 255.0 / 360.0, sat * 255.0, val * 255.0], axis=-1)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), mode="HSV").convert("RGB")


def recolour(im: Image.Image, treatment: str | None) -> Image.Image:
    if treatment is None:
        return im.convert("RGB")
    if treatment == "greyscale":
        return im.convert("L").convert("RGB")
    if treatment == "contour_blue":
        # orange or red contour on a grey CT -> radiology blue
        return snap_hues(im, style.RADIOLOGY_IMAGING, sat_floor=0.85)
    if treatment == "overlay_blue":
        # multi-hue organ overlay -> one blue ramp; organs stay apart by lightness
        return snap_hues(im, style.RADIOLOGY_IMAGING, sat_floor=0.55)
    if treatment == "pet_orange":
        # "hot" colormap PET fused on CT -> molecular orange ramp
        return snap_hues(im, style.MOLECULAR, hue_lo=330, hue_hi=75, sat_floor=0.7)
    if treatment == "lesion_orange":
        return snap_hues(im, style.MOLECULAR, hue_lo=300, hue_hi=60, sat_floor=0.9)
    if treatment == "bars_grey":
        # transparent-background histogram in steel blue -> bar ink on white
        rgba = im.convert("RGBA")
        arr = np.asarray(rgba).copy()
        alpha = arr[..., 3:4].astype(np.float32) / 255.0
        ink = np.array([int(style.BAR_FILL[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)
        rgb = ink * alpha + 255.0 * (1.0 - alpha)
        return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
    raise ValueError(f"unknown recolour treatment {treatment!r}")


def panel_image(key: str, w_in: float, h_in: float) -> Image.Image:
    """Load, crop, recolour, and fit one panel to its print size."""
    rel, fit, crop, treatment = SLOTS[key]
    src = PANELS / rel
    if not src.is_file():
        raise FileNotFoundError(f"missing panel {src}")
    im = Image.open(src)
    if im.mode in ("RGBA", "LA") and treatment != "bars_grey":
        im = Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im.convert("RGBA"))
    im = recolour(im, treatment)
    if crop:
        l, t, r, b = crop
        im = im.crop((int(l * im.width), int(t * im.height), int(r * im.width), int(b * im.height)))
    box = (max(8, int(round(w_in * PANEL_PPI))), max(8, int(round(h_in * PANEL_PPI))))
    if fit == "cover":
        return ImageOps.fit(im, box, Image.LANCZOS)
    return ImageOps.pad(im, box, Image.LANCZOS, (255, 255, 255))


# --------------------------------------------------------------------------
# Icons. The 37 hand-authored icons are 24-unit line icons at 0.5-unit stroke.
# At 0.26 in that stroke prints at 0.4 pt, on the guide's floor and lighter
# than the project's Noun Project icons, so the stroke is raised to 1.1 units
# before rasterizing (author's decision, docs/DECISIONS.md). ``currentColor``
# becomes the tint. The project's own icons are used as they are.
# --------------------------------------------------------------------------
ICON_STROKE = "1.1"


def icon_image(name: str, tint: str = style.INK) -> Image.Image:
    if name.startswith("noun_"):
        src = PROJECT_ICONS / f"{name}.svg"
    else:
        src = ICONS / f"{name}.svg"
    if not src.is_file():
        raise FileNotFoundError(f"missing icon {src}")
    svg = src.read_text(encoding="utf-8")
    svg = re.sub(r"<title>.*?</title>", "", svg, flags=re.S)
    svg = svg.replace("currentColor", tint)
    svg = svg.replace('stroke-width="0.5"', f'stroke-width="{ICON_STROKE}"')
    if name.startswith("noun_"):
        # Noun Project icons are filled black shapes; tint the fill.
        svg = re.sub(r'fill="#000000"|fill="#000"|fill="black"', f'fill="{tint}"', svg)
        if "fill=" not in svg.split(">", 1)[1][:4000]:
            svg = svg.replace("<svg", f'<svg fill="{tint}"', 1)
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=ICON_PX, output_height=ICON_PX)
    return Image.open(io.BytesIO(png)).convert("RGBA")


# --------------------------------------------------------------------------
# Drawing helpers. Coordinates are inches from the top-left of the page.
# --------------------------------------------------------------------------

NEUTRAL_BORDER = "#20242B"


def text_width_in(text: str, size: float, *, weight: str = "normal", italic: bool = False,
                  family: str = style.SANS) -> float:
    """Width of one line of text in inches, measured in the vendored face."""
    prop = FontProperties(family=family, weight=weight, style="italic" if italic else "normal", size=size)
    return TextPath((0, 0), text, size=size, prop=prop).get_extents().width / 72.0


def wrap(text: str, size: float, width_in: float, **kw) -> list[str]:
    """Greedy word wrap against a measured width."""
    lines: list[str] = []
    current: list[str] = []
    for word in text.split():
        trial = " ".join(current + [word])
        if current and text_width_in(trial, size, **kw) > width_in:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


class Overflow(RuntimeError):
    """Content ran past the space reserved for it."""


def fit(name: str, text: str, size: float, width_in: float, **kw) -> None:
    """Raise if any line of ``text`` is wider than ``width_in``."""
    for line in text.split("\n"):
        w = text_width_in(line, size, **kw)
        if w > width_in + 0.002:
            raise Overflow(f"{name}: {line!r} is {w:.3f} in at {size} pt, space is {width_in:.3f} in")


class Canvas:
    def __init__(self, figure: Figure):
        self.fig = figure
        self.trans = figure.dpi_scale_trans

    def _y(self, y_top: float, h: float = 0.0) -> float:
        return H_IN - y_top - h

    def text(self, x, y, s, size, *, weight="normal", family="sans-serif", color=style.INK,
             ha="left", va="top", italic=False, linespacing=1.15, zorder=5):
        return self.fig.text(x, self._y(y), s, transform=self.trans, fontsize=size, fontweight=weight,
                             fontfamily=family, color=color, ha=ha, va=va,
                             fontstyle="italic" if italic else "normal", linespacing=linespacing,
                             zorder=zorder)

    def box(self, x, y, w, h, *, edge, lw, radius=0.0, fill="#FFFFFF", dashed=False, zorder=1):
        if radius > 0:
            patch = FancyBboxPatch((x, self._y(y, h)), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
                                   transform=self.trans, linewidth=lw, edgecolor=edge, facecolor=fill,
                                   zorder=zorder, linestyle=(0, (4, 3)) if dashed else "solid")
        else:
            patch = Rectangle((x, self._y(y, h)), w, h, transform=self.trans, linewidth=lw, edgecolor=edge,
                              facecolor=fill, zorder=zorder, linestyle=(0, (4, 3)) if dashed else "solid")
        self.fig.add_artist(patch)
        return patch

    def image(self, x, y, w, h, im: Image.Image, *, border=None, lw=LW_HAIR):
        ax = self.fig.add_axes([x / W_IN, self._y(y, h) / H_IN, w / W_IN, h / H_IN])
        ax.imshow(np.asarray(im), aspect="auto", interpolation="lanczos")
        ax.set_axis_off()
        ax.set_zorder(1.5)  # above a card's white fill (1), below its border (2)
        if border:
            self.box(x, y, w, h, edge=border, lw=lw, fill="none", zorder=2)
        return ax

    def icon(self, x, y, size, name, *, tint=style.INK):
        return self.image(x, y, size, size, icon_image(name, tint))

    def arrow(self, x1, y1, x2, y2, *, lw=LW_ARROW, color=style.LINE, dashed=False, head=6.5):
        patch = FancyArrowPatch((x1, self._y(y1)), (x2, self._y(y2)), transform=self.trans, arrowstyle="-|>",
                                mutation_scale=head, linewidth=lw, color=color, shrinkA=0, shrinkB=0,
                                linestyle=(0, (4, 3)) if dashed else "solid", zorder=4)
        self.fig.add_artist(patch)
        return patch

    def polyline(self, points, *, lw=LW_ARROW, color=style.LINE, dashed=False, zorder=4):
        verts = [(x, self._y(y)) for x, y in points]
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * (len(verts) - 1)
        patch = PathPatch(MplPath(verts, codes), transform=self.trans, fill=False, linewidth=lw,
                          edgecolor=color, linestyle=(0, (4, 3)) if dashed else "solid", zorder=zorder,
                          capstyle="butt", joinstyle="round")
        self.fig.add_artist(patch)
        return patch

    def badge(self, cx, cy, n: int, r=0.058):
        self.fig.add_artist(Circle((cx, self._y(cy)), r, transform=self.trans, facecolor="#FFFFFF",
                                   edgecolor=style.INK, linewidth=0.6, zorder=4))
        self.text(cx, cy + 0.003, str(n), FS_BADGE, weight="bold", ha="center", va="center", zorder=5)

    def card(self, x, y, w, h, label, sub=None, *, edge=NEUTRAL_BORDER, lw=LW_NEUTRAL, bold=False,
             sub_color=style.SUBTLE, icon=None, icon_tint=style.INK, radius=0.02, align="left",
             label_size=FS_CARD):
        """A white card with a hairline border, a label, and an optional sub-label.

        ``label`` may hold newlines. Text is stacked and centred vertically;
        ``align`` centres it horizontally as well.
        """
        self.box(x, y, w, h, edge=edge, lw=lw, radius=radius)
        tx = x + 0.06
        if icon:
            isz = min(h - 0.08, 0.20)
            self.icon(x + 0.05, y + (h - isz) / 2, isz, icon, tint=icon_tint)
            tx = x + 0.05 + isz + 0.05
        if align == "center":
            tx = x + w / 2 if not icon else (tx + x + w - 0.04) / 2
        n_lines = label.count("\n") + 1
        block = n_lines * label_size * 1.15 + (FS_CARD_SUB * 1.2 if sub else 0)
        top = y + h / 2 - block / 2 / 72
        self.text(tx, top, label, label_size, weight="bold" if bold else "normal", va="top",
                  ha=align, linespacing=1.1)
        if sub:
            self.text(tx, top + n_lines * label_size * 1.15 / 72 + 0.01, sub, FS_CARD_SUB, color=sub_color,
                      va="top", ha=align)





CREDIT_TEXT = (
    "Panels rendered from openly licensed imaging data, all CC BY 4.0 or CC0: TotalSegmentator (Zenodo 10047292) · "
    "AMOS22 (Zenodo 7262581) · FDG-PET-CT-Lesions / autoPET v2, TCIA (doi:10.7937/gkr0-xv29) · CMMD, TCIA "
    "(doi:10.7937/tcia.eqde-4b16) · B-mode-and-CEUS-Liver, TCIA (doi:10.7937/TCIA.2021.v4z7-tc39) · chest "
    "radiograph, Mikael Häggström, Wikimedia Commons, CC0. Icons hand-authored."
)
CREDIT_NOTE = (
    "Segmentation appears twice on purpose, as ROI extraction in preprocessing and as an endpoint in clinical "
    "tasks. The dashed link marks the inversion argued in R.1."
)
CREDIT_LINES = wrap(CREDIT_TEXT, FS_CREDIT, FRAME_W - 0.02) + wrap(CREDIT_NOTE, FS_CREDIT, FRAME_W - 0.02)
CREDIT_H = len(CREDIT_LINES) * FS_CREDIT * 1.3 / 72
H_IN = CREDIT_TOP + CREDIT_H + 16 * K
FIGURE_SIZE = (W_IN, H_IN)


# --------------------------------------------------------------------------
# The figure. Each column is drawn with a vertical cursor from the top of its
# box's content area; the cursor's final value is checked against the box so
# an overflow fails the build instead of printing past a border.
# --------------------------------------------------------------------------

@dataclass
class Layout:
    """Positions other parts of the drawing need to know about."""
    seg_group_x_centre: float = 0.0
    seg_group_bottom: float = 0.0
    task_seg_y_centre: float = 0.0
    task_x_left: float = 0.0


def _check(name: str, y_end: float) -> None:
    limit = CONTENT_Y0 + CONTENT_H
    print(f"  {name:<14} content ends {y_end:.3f} in, box ends {limit:.3f} in, slack {limit - y_end:+.3f}")
    if y_end > limit + 0.002:
        raise Overflow(f"{name}: content ends {y_end:.3f} in below box end {limit:.3f} in")


def draw_frame(cv: Canvas) -> None:
    # Section title above the frame, as in the original, set as the panel
    # letter and title the style guide asks for.
    cv.text(FRAME_X, TOP - 0.01, "A", FS_LETTER, weight="bold", family="serif")
    cv.text(FRAME_X + 0.24, TOP + 0.02, "Radiology", FS_TITLE, weight="bold", family="serif")
    # The frame: the guide's panel border.
    cv.box(FRAME_X, FRAME_TOP, FRAME_W, FRAME_BOTTOM - FRAME_TOP, edge=NEUTRAL_BORDER, lw=LW_PANEL,
           radius=0.05, zorder=-1)
    # Header row.
    y_head = FRAME_TOP + FRAME_PAD_T
    for x, title in zip(COL_X, ("Input Data", "Preprocessing", "Models", "Clinical Tasks")):
        cv.text(x, y_head, title, FS_SUBTITLE, weight="bold", family="serif")
    cv.text(COL_X[3], y_head + 0.125, "along the care pathway", FS_CAPTION, color=style.SUBTLE, italic=True)
    # The four column boxes. Dashed, as in the original: a dashed stroke is the
    # guide's mark for a conceptual boundary, which a column grouping is.
    for x, w in zip(COL_X, COL_W):
        cv.box(x, BOX_TOP, w, BOX_H, edge=NEUTRAL_BORDER, lw=LW_NEUTRAL, dashed=True, fill="none", zorder=0.5)


def _brace(cv: Canvas, x: float, y: float, w: float, lines: list[tuple[str, str]]) -> float:
    """The original's caption: a rule across the group, then centred lines.

    Each line is (text, colour). Returns the y below the last line.
    """
    cv.polyline([(x, y), (x + w, y)], lw=LW_HAIR, color=style.RULE, zorder=2)
    yy = y + 0.035
    for text, colour in lines:
        cv.text(x + w / 2, yy, text, FS_CAPTION, color=colour, ha="center")
        yy += FS_CAPTION * 1.25 / 72
    return yy


def _strip(cv: Canvas, x: float, y: float, w: float, heading: str, body_lines: list[str]) -> float:
    """A bordered strip with a bold heading and subtle body text; returns its bottom."""
    pad = 0.025
    body_h = len(body_lines) * FS_CAPTION * 1.18 / 72
    h = pad + 0.08 + 0.005 + body_h + pad
    cv.box(x, y, w, h, edge=NEUTRAL_BORDER, lw=LW_NEUTRAL, radius=0.01)
    cv.text(x + 0.04, y + pad, heading, FS_ICON_LABEL, weight="bold")
    cv.text(x + 0.04, y + pad + 0.085, "\n".join(body_lines), FS_CAPTION, color=style.SUBTLE, linespacing=1.18)
    return y + h


def draw_input_column(cv: Canvas) -> None:
    x0 = COL_X[0] + BOX_PAD_X
    cw_content = COL_W[0] - 2 * BOX_PAD_X
    tw, gap = 0.46, 0.16
    grid_x = x0 + (cw_content - (2 * tw + gap)) / 2
    cards = [
        ("mod_xray", "Radiography", "2D projection"),
        ("mod_mammo", "Mammography", "2D · DBT"),
        ("mod_us", "Ultrasound", "real-time video"),
        ("mod_ct", "CT", "3D · structural"),
        ("mod_mri", "MRI", "3D · T1/T2/DWI"),
        ("mod_pet", "PET", "molecular · SUV"),
    ]
    text_block = 0.025 + FS_MOD_LABEL / 72 + 0.012 + FS_CARD_SUB / 72
    pitch = tw + text_block + 0.03
    y = CONTENT_Y0
    for i, (key, label, sub) in enumerate(cards):
        cx = grid_x + (i % 2) * (tw + gap)
        cy = y + (i // 2) * pitch
        cv.image(cx, cy, tw, tw, panel_image(key, tw, tw), border=style.RADIOLOGY_IMAGING, lw=LW_CARD)
        fit(f"modality label {label}", label, FS_MOD_LABEL, tw + gap - 0.02, weight="bold")
        fit(f"modality sub-label {sub}", sub, FS_CARD_SUB, tw + gap - 0.02)
        cv.text(cx + tw / 2, cy + tw + 0.025, label, FS_MOD_LABEL, weight="bold", ha="center")
        cv.text(cx + tw / 2, cy + tw + 0.025 + FS_MOD_LABEL / 72 + 0.012, sub, FS_CARD_SUB,
                color=style.RADIOLOGY_IMAGING_DEEP, ha="center")
    y = y + 3 * pitch - 0.03 + 0.035
    body_w = cw_content - 0.08
    y = _strip(cv, x0, y, cw_content, "Dimensionality", wrap(
        "2D projection · quasi-3D (DBT) · 3D volumetric (CT, MRI, PET) · 2D + time (ultrasound, cine MR) · "
        "4D (DCE-MR, 4D CT)", FS_CAPTION, body_w))
    y = _strip(cv, x0, y + 0.035, cw_content, "Paired non-image data", wrap(
        "report text · DICOM metadata · clinical and staging · molecular", FS_CAPTION, body_w))
    _check("input data", y)


def _thumbs(cv: Canvas, x: float, y: float, keys: list[str], tw: float, th: float, gap: float) -> float:
    for j, key in enumerate(keys):
        cv.image(x + j * (tw + gap), y, tw, th, panel_image(key, tw, th), border=style.RULE, lw=LW_HAIR)
    return x + len(keys) * tw + (len(keys) - 1) * gap


def draw_preprocessing_column(cv: Canvas, layout: Layout) -> None:
    x0 = COL_X[1] + BOX_PAD_X
    cw = COL_W[1] - 2 * BOX_PAD_X
    y = CONTENT_Y0
    # Head chips.
    chip_w = (cw - 0.06) / 2
    cv.card(x0, y, chip_w, 0.33, "DICOM parse,\nseries selection,\nde-identify", icon="pre-dicom",
            label_size=FS_ICON_LABEL)
    cv.card(x0 + chip_w + 0.06, y, chip_w, 0.33, "scanner / site\nharmonization\n(ComBat)", icon="pre-harmonize",
            label_size=FS_ICON_LABEL)
    y += 0.33 + 0.06
    # Intensity standardization.
    cv.text(x0, y, "Intensity standardization", FS_BLOCK, weight="bold")
    y += 0.13
    tw, th, g = 0.468, 0.46, 0.03
    right = _thumbs(cv, x0, y, ["w_full", "w_lung", "w_medi"], tw, th, g)
    b1 = _brace(cv, x0, y + th + 0.03, right - x0, [("CT: window / level", style.SUBTLE),
                                                    ("full range, lung, mediastinum", style.SUBTLE)])
    gx = right + 0.06
    right2 = _thumbs(cv, gx, y, ["mr_raw", "mr_z"], tw, th, g)
    _brace(cv, gx, y + th + 0.03, right2 - gx, [("MRI: z-score, N4 · PET: SUV", style.SUBTLE)])
    y = b1 + 0.06
    # Geometry.
    cv.text(x0, y, "Geometry", FS_BLOCK, weight="bold")
    y += 0.13
    th = 0.33
    right = _thumbs(cv, x0, y, ["sp_native", "sp_iso"], 0.44, th, 0.025)
    b1 = _brace(cv, x0, y + th + 0.03, right - x0, [("resampling", style.SUBTLE),
                                                    ("3.0 mm to 1 mm isotropic", style.SUBTLE)])
    gx = right + 0.045
    right = _thumbs(cv, gx, y, ["pl_ax", "pl_cor", "pl_sag"], 0.29, th, 0.025)
    _brace(cv, gx, y + th + 0.03, right - gx, [("orientation and 2.5D", style.SUBTLE),
                                               ("3 planes, adjacent slices", style.SUBTLE)])
    gx = right + 0.045
    right = _thumbs(cv, gx, y, ["mip_1", "mip_60"], 0.29, th, 0.025)
    _brace(cv, gx, y + th + 0.03, right - gx, [("MIP (optional)", style.SUBTLE),
                                               ("slice to 60 mm slab", style.SUBTLE)])
    y = b1 + 0.06
    # Registration and segmentation.
    th = 0.40
    cv.text(x0, y, "Registration", FS_BLOCK, weight="bold")
    right = _thumbs(cv, x0, y + 0.13, ["reg_before", "reg_after", "reg_fused"], 0.39, th, 0.025)
    _brace(cv, x0, y + 0.13 + th + 0.03, right - x0, [("longitudinal · inter-modality · atlas", style.SUBTLE),
                                                     ("rigid / deformable", style.SUBTLE)])
    sx = right + 0.06
    cv.text(sx, y, "Segmentation to ROI / VOI", FS_BLOCK, weight="bold")
    seg_right = _thumbs(cv, sx, y + 0.13, ["seg_in", "seg_ov", "seg_mask"], 0.39, th, 0.025)
    b2 = _brace(cv, sx, y + 0.13 + th + 0.03, seg_right - sx, [("anatomy crop, then lesion VOI", style.SUBTLE),
                                                              ("also a clinical task", style.INK)])
    layout.seg_group_x_centre = (sx + seg_right) / 2
    layout.seg_group_bottom = b2
    _check("preprocessing", b2)


def _icon_row(cv: Canvas, x: float, y: float, cells: list[tuple[str, str]], cell_w: float = 0.50,
              icon_sz: float = 0.22) -> float:
    n_lines = max(label.count("\n") + 1 for _, label in cells)
    for j, (name, label) in enumerate(cells):
        cx = x + j * (cell_w + 0.06)
        cv.icon(cx + (cell_w - icon_sz) / 2, y, icon_sz, name)
        cv.text(cx + cell_w / 2, y + icon_sz + 0.025, label, FS_CAPTION, ha="center", linespacing=1.1)
    return y + icon_sz + 0.025 + n_lines * FS_CAPTION * 1.1 / 72


def draw_models_column(cv: Canvas) -> None:
    x0 = COL_X[2] + BOX_PAD_X
    cw = COL_W[2] - 2 * BOX_PAD_X
    y = CONTENT_Y0
    # 1 Pre-defined features
    cv.badge(x0 + 0.058, y + 0.06, 1)
    cv.text(x0 + 0.17, y, "Pre-defined features", FS_BLOCK, weight="bold")
    y += 0.16
    th = 0.40
    cv.image(x0, y, 0.514, th, panel_image("roi", 0.514, th), border=style.RULE, lw=LW_HAIR)
    cv.image(x0 + 0.546, y, 0.514, th, panel_image("hist", 0.514, th), border=style.RULE, lw=LW_HAIR)
    cv.image(x0 + 1.092, y, 0.471, th, panel_image("glcm", 0.471, th), border=style.RULE, lw=LW_HAIR)
    y += th + 0.03
    cv.text(x0, y, "real VOI · its HU histogram · its 32-bin GLCM", FS_CAPTION, color=style.SUBTLE)
    y += 0.12
    c1w, c2w, ch = 0.95, 0.62, 0.38
    cv.card(x0, y, c1w, ch, "IBSI: first-order, shape,\ntexture (GLCM, GLRLM,\nGLSZM, NGTDM),\nwavelet / LoG",
            label_size=FS_CAPTION)
    cv.arrow(x0 + c1w + 0.02, y + ch / 2, x0 + c1w + 0.11, y + ch / 2)
    cv.card(x0 + c1w + 0.13, y, c2w, ch, "selection +\nclassical ML\n(LASSO, RF, Cox)", label_size=FS_CAPTION,
            align="center")
    y += ch + 0.09
    # 2 Supervised deep learning
    cv.badge(x0 + 0.058, y + 0.06, 2)
    cv.text(x0 + 0.17, y, "Supervised deep learning", FS_BLOCK, weight="bold")
    y += 0.16
    y = _icon_row(cv, x0, y, [("mdl-cnn", "CNN"), ("mdl-unet", "U-Net\nencoder-decoder"), ("mdl-vit", "ViT")])
    y += 0.06
    # 3 Self-supervised and foundation
    cv.badge(x0 + 0.058, y + 0.06, 3)
    cv.text(x0 + 0.17, y, "Self-supervised and foundation", FS_BLOCK, weight="bold")
    y += 0.16
    y = _icon_row(cv, x0, y, [("mdl-ssl", "SSL\npretraining"), ("mdl-foundation", "foundation\nmodel"),
                              ("mdl-vlm", "vision-\nlanguage")])
    y += 0.07
    # Task head
    cv.icon(x0, y + 0.07, 0.20, "mdl-head")
    cv.text(x0 + 0.28, y, "Task head", FS_CARD, weight="bold")
    cv.card(x0 + 0.28, y + 0.12, cw - 0.28, 0.27, "linear · Cox · segmentation decoder ·\ntext decoder",
            label_size=FS_CAPTION)
    y += 0.12 + 0.27 + 0.04
    cv.text(x0, y, "one backbone, many tasks; the head decides which", FS_CAPTION, color=style.SUBTLE)
    y += FS_CAPTION / 72
    _check("models", y)


def draw_tasks_column(cv: Canvas, layout: Layout) -> None:
    x0 = COL_X[3] + BOX_PAD_X
    tasks = [
        ("Screening /\nfuture risk", "t_screen", None),
        ("Triage /\nworkflow", None, "task-triage"),
        ("Detection /\nlocalization", "t_detect", None),
        ("Segmentation /\nquantification", "t_seg", None),
        ("Diagnosis /\ncharacterization", None, "task-classify"),
        ("Radiogenomics /\nmolecular", None, "task-radiogenomics"),
        ("Treatment\nplanning", None, "task-rtplan"),
        ("Response /\nlongitudinal", "t_resp", None),
        ("Prognosis /\nsurvival", None, "task-prognosis"),
        ("Report\ngeneration / VQA", None, "task-report"),
    ]
    box, pitch = 0.204, 0.231          # the original's 38 px rows on a 43 px pitch
    spine_x = x0 + 0.025
    rows_h = len(tasks) * pitch - (pitch - box)
    cv.arrow(spine_x, CONTENT_Y0 + 0.02, spine_x, CONTENT_Y0 + rows_h, color=style.LINE, lw=0.5, head=5)
    bx = x0 + 0.085
    for i, (label, img, ic) in enumerate(tasks):
        ty = CONTENT_Y0 + i * pitch
        if img:
            cv.image(bx, ty, box, box, panel_image(img, box, box), border=NEUTRAL_BORDER, lw=LW_NEUTRAL)
        else:
            cv.box(bx, ty, box, box, edge=NEUTRAL_BORDER, lw=LW_NEUTRAL, radius=0.01)
            cv.icon(bx + 0.03, ty + 0.03, box - 0.06, ic)
        label_w = COL_X[3] + COL_W[3] - BOX_PAD_X - (bx + box + 0.03)
        fit(f"task label {label!r}", label, FS_TASK, label_w)
        cv.text(bx + box + 0.03, ty + box / 2, label, FS_TASK, va="center", linespacing=1.08)
        if img == "t_seg":
            layout.task_seg_y_centre = ty + box / 2
            layout.task_x_left = bx
    _check("clinical tasks", CONTENT_Y0 + rows_h)


def draw_link(cv: Canvas, layout: Layout) -> None:
    """Dashed link from segmentation-as-preprocessing to segmentation-as-task.

    Runs in the frame's bottom padding, as in the original, with its note.
    """
    yb = BOX_TOP + BOX_H + 12 * K
    xg = COL_X[2] + COL_W[2] + COL_GAP / 2
    x1 = layout.seg_group_x_centre
    cv.polyline([(x1, layout.seg_group_bottom + 0.01), (x1, yb), (xg, yb), (xg, layout.task_seg_y_centre)],
                dashed=True, lw=0.6)
    cv.arrow(xg, layout.task_seg_y_centre, layout.task_x_left - 0.015, layout.task_seg_y_centre,
             dashed=True, lw=0.6, head=5.5)
    cv.text(x1 + 0.075, yb + 0.04, "the same segmentation, once as ROI extraction and once as an endpoint",
            FS_CAPTION, color=style.SUBTLE, italic=True)


def draw_credit(cv: Canvas) -> None:
    cv.text(FRAME_X, CREDIT_TOP, "\n".join(CREDIT_LINES), FS_CREDIT, color=style.SUBTLE, linespacing=1.3)


def build_figure() -> Figure:
    figure = plt.figure(figsize=FIGURE_SIZE)
    cv = Canvas(figure)
    layout = Layout()
    draw_frame(cv)
    print("column fit:")
    draw_input_column(cv)
    draw_preprocessing_column(cv, layout)
    draw_models_column(cv)
    draw_tasks_column(cv, layout)
    draw_link(cv, layout)
    draw_credit(cv)
    return figure


def summary_text(output_dir: Path) -> str:
    lines = [
        f"{OUTPUT_STEM} — build summary",
        f"figure size      : {FIGURE_SIZE[0]} x {FIGURE_SIZE[1]:.2f} in (aspect {FIGURE_SIZE[0]/FIGURE_SIZE[1]:.2f}; original PDF page 1.74)",
        f"columns (in)     : {', '.join(f'{w:.3f}' for w in COL_W)}; gap {COL_GAP:.3f}; box height {BOX_H:.3f}",
        f"type ladder (pt) : letter {FS_LETTER}, title {FS_TITLE}, subtitle {FS_SUBTITLE}, block {FS_BLOCK}, "
        f"card {FS_CARD}, task {FS_TASK}, icon label {FS_ICON_LABEL}, caption {FS_CAPTION}, "
        f"card sub {FS_CARD_SUB}; smallest {min(FS_CARD_SUB, FS_CAPTION)}",
        f"panel raster     : {PANEL_PPI} px per inch of print; icons {ICON_PX} px, stroke raised 0.5 -> {ICON_STROKE}",
        "",
        "Panel slots and sources (every source CC BY 4.0 or CC0):",
        f"  {'slot':<11}{'file':<58}{'treatment':<15}source",
    ]
    for key, (rel, fit, crop, treatment) in SLOTS.items():
        source, licence = SOURCES.get(rel, ("UNKNOWN", "UNKNOWN"))
        lines.append(f"  {key:<11}{rel:<58}{(treatment or '-'):<15}{source} ({licence})")
    lines += [
        "",
        "Colour treatments: contour_blue and overlay_blue snap every saturated hue to radiology",
        "blue #0072B2; pet_orange and lesion_orange snap PET signal to molecular orange #E69F00;",
        "bars_grey paints histogram bars in bar ink #3D4147; greyscale drops hue entirely.",
        "",
        "Icons: 37 hand-authored icons from assets/icons (ink), plus the",
        "project's noun_medicinedocument (clinical text deep #006B4E) and noun_DNA (molecular deep #9C6C00).",
        "",
        "Structure kept from the original at the author's instruction (2026-09-04): frame, four dashed",
        "column boxes, header row, both strips, chips, brace captions, dashed link with its note, credits.",
        "",
    ]
    return "\n".join(lines)


def build(output_dir: str | Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(style.rc_params()):
        figure = build_figure()
        paths = {ext: output_dir / f"{OUTPUT_STEM}.{ext}" for ext in ("pdf", "png", "svg")}
        figure.savefig(paths["pdf"])
        figure.savefig(paths["png"], dpi=300)
        figure.savefig(paths["svg"])
        plt.close(figure)
    paths["summary"] = output_dir / f"{OUTPUT_STEM}_summary.txt"
    paths["summary"].write_text(summary_text(output_dir), encoding="utf-8")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default=str(HERE / "figures"), help="directory for the outputs")
    args = parser.parse_args(argv)
    for name, path in build(args.output).items():
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
