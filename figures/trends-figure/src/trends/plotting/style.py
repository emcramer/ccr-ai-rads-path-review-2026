"""Canonical keys, labels, and visual style for the trends figure.

Every key and every display label in this module comes from the "Canonical keys"
section of ``docs/figure-spec.md``. They are repeated here, rather than imported
from ``trends.config``, because the plotting code is required to depend on
nothing but the three processed tables. If the retrieval package later exposes
the same registry, the two should be reconciled and one of them deleted.

Colour choices
--------------
The four theme colours are drawn from the Okabe-Ito palette, which is
distinguishable under the three common forms of colour vision deficiency. Four
categorical hues cannot also be four clearly separated grey values, so colour
never carries information alone:

* Panel A is legible with no colour at all. The matrix, the block order, and the
  bar heights carry the content; the theme colour only tints the bars.
* Panel B gives every line its own dash pattern, its own marker, and a label at
  the end of the line. The two clinical lines share a colour and differ by dash,
  as the specification requires.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# Canonical keys
# --------------------------------------------------------------------------

#: Theme keys in the left-to-right block order used by Panel A.
THEME_ORDER: Final[tuple[str, ...]] = (
    "foundation_models",
    "multimodal_integration",
    "digital_twins",
    "clinical_fda",
)

#: Display label for each theme key. Long labels are wrapped by the drawing code.
THEME_LABELS: Final[dict[str, str]] = {
    "foundation_models": "Foundation Models",
    "multimodal_integration": "Multimodal Integration",
    "digital_twins": "Digital Twins",
    "clinical_fda": "Clinical Applications /\nFDA Approval",
}

#: Modality keys in figure row order: pathology, then radiology, then the
#: non-imaging data types, then ``other``.
MODALITY_ORDER: Final[tuple[str, ...]] = (
    "he_histology",
    "ihc",
    "spatial_proteomics",
    "spatial_transcriptomics",
    "pathology_report",
    "mri",
    "ct",
    "pet",
    "ultrasound",
    "mammography",
    "xray",
    "radiology_report",
    "genomics",
    "clinical_data",
    "other",
)

#: Display label for each modality key, used on the shared row axis.
MODALITY_LABELS: Final[dict[str, str]] = {
    "he_histology": "H&E / Histology",
    "ihc": "IHC",
    "spatial_proteomics": "Spatial Proteomics",
    "spatial_transcriptomics": "Spatial Transcriptomics",
    "pathology_report": "Pathology Report",
    "mri": "MRI",
    "ct": "CT",
    "pet": "PET",
    "ultrasound": "Ultrasound",
    "mammography": "Mammography",
    "xray": "Radiography (X-ray)",
    "radiology_report": "Radiology Report",
    "genomics": "Genomics / Transcriptomics",
    "clinical_data": "Clinical / EHR Data",
    "other": "Other",
}

#: Modality keys that make a paper radiological, per the ``domain`` rule in the spec.
RADIOLOGY_MODALITIES: Final[frozenset[str]] = frozenset(
    {"mri", "ct", "pet", "ultrasound", "mammography", "xray", "radiology_report"}
)

#: Modality keys that make a paper pathological, per the ``domain`` rule in the spec.
PATHOLOGY_MODALITIES: Final[frozenset[str]] = frozenset(
    {"he_histology", "ihc", "spatial_proteomics", "spatial_transcriptomics", "pathology_report"}
)

# ``genomics``, ``clinical_data`` and ``other`` appear in neither set, and that is
# deliberate: they are not imaging, so they cannot make a paper radiologic or
# pathologic. A paper using MRI and genomics is ``radiology``, not ``both``. They
# earn matrix rows because pairing imaging with molecular or clinical data is the
# multimodal integration the review argues about, and it is invisible without a
# row to draw it on. See the canonical-keys section of ``docs/figure-spec.md``.

#: Permitted values of the ``domain`` column of ``theme_year_counts.csv``.
DOMAIN_VALUES: Final[frozenset[str]] = frozenset({"all", "radiology", "pathology"})

# --------------------------------------------------------------------------
# Colour and line style
# --------------------------------------------------------------------------

#: Okabe-Ito hue per theme.
THEME_COLORS: Final[dict[str, str]] = {
    "foundation_models": "#0072B2",       # blue
    "multimodal_integration": "#E69F00",  # orange
    "digital_twins": "#009E73",           # bluish green
    "clinical_fda": "#D55E00",            # vermillion
}

#: Darker variant of each theme colour, for small text.
#: The bright hues above are fine as bar fills, which are large areas, but orange
#: and green at 7 pt on white are too light to read and too pale in greyscale.
#: These variants keep the colour link between a line and its label while
#: staying legible in print.
THEME_TEXT_COLORS: Final[dict[str, str]] = {
    "foundation_models": "#005E93",
    "multimodal_integration": "#8A6000",
    "digital_twins": "#00694C",
    "clinical_fda": "#A54900",
}

#: Dash pattern per Panel B series. The clinical theme's two domain lines share a
#: colour and are told apart by dash alone, as the specification requires.
SERIES_DASHES: Final[dict[tuple[str, str], tuple]] = {
    ("foundation_models", "all"): (0, ()),
    ("multimodal_integration", "all"): (0, (6, 1.6)),
    ("digital_twins", "all"): (0, (1, 1.5)),
    ("clinical_fda", "radiology"): (0, (5, 1.2, 1, 1.2)),
    ("clinical_fda", "pathology"): (0, (2.4, 1.4)),
}

#: Marker per Panel B series, a second non-colour cue.
SERIES_MARKERS: Final[dict[tuple[str, str], str]] = {
    ("foundation_models", "all"): "o",
    ("multimodal_integration", "all"): "s",
    ("digital_twins", "all"): "^",
    ("clinical_fda", "radiology"): "D",
    ("clinical_fda", "pathology"): "v",
}

#: Suffix appended to the theme label for a domain-split line.
DOMAIN_SUFFIX: Final[dict[str, str]] = {
    "all": "",
    "radiology": " (radiology)",
    "pathology": " (pathology)",
}

#: End-of-line label for each Panel B series, pre-wrapped to fit the right margin.
#: Panel B labels lines directly instead of using a legend box, so these strings
#: must stay short enough that five of them fit beside the axes without colliding.
SERIES_END_LABELS: Final[dict[tuple[str, str], str]] = {
    ("foundation_models", "all"): "Foundation Models",
    ("multimodal_integration", "all"): "Multimodal\nIntegration",
    ("digital_twins", "all"): "Digital Twins",
    ("clinical_fda", "radiology"): "Clinical Applications /\nFDA Approval (radiology)",
    ("clinical_fda", "pathology"): "Clinical Applications /\nFDA Approval (pathology)",
}

# Neutral inks. Kept together so a journal illustrator can retune them in one place.
INK: Final[str] = "#1A1A1A"          # present dots, connectors, axis text
INK_LIGHT: Final[str] = "#D6D6D6"    # absent dots
BAND: Final[str] = "#F2F2F2"         # alternating matrix row bands
RULE: Final[str] = "#9A9A9A"         # block separators, axis spines
PARTIAL_BAND: Final[str] = "#E9E9E9"  # shading over the partial final year

# --------------------------------------------------------------------------
# Type sizes, in points
# --------------------------------------------------------------------------

FS_PANEL_LETTER: Final[float] = 11.0
FS_THEME_TITLE: Final[float] = 7.2
FS_AXIS_LABEL: Final[float] = 7.5
FS_TICK: Final[float] = 7.0
FS_BAR_VALUE: Final[float] = 5.5
FS_NOTE: Final[float] = 5.8
FS_SERIES_LABEL: Final[float] = 7.0


def rc_params() -> dict:
    """Return the matplotlib rcParams the figure is drawn under.

    Fonts are embedded as TrueType (``fonttype`` 42) rather than as Type 3
    subsets, so the PDF stays editable by the journal's illustrator.
    """
    return {
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
        "font.size": FS_TICK,
        "axes.linewidth": 0.6,
        "axes.edgecolor": RULE,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.2,
        "ytick.major.size": 2.2,
        "lines.solid_capstyle": "round",
        # The remainder bar is hatched. The default hatch line is heavy enough at
        # 300 dpi to fill a narrow bar solid, which would hide that it is hollow.
        "hatch.linewidth": 0.4,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "figure.dpi": 100,
        "savefig.dpi": 300,
    }


def theme_text_color(theme: str) -> str:
    """Return the small-text colour for ``theme``, dark enough to read on white."""
    return THEME_TEXT_COLORS.get(theme, INK)


def theme_label(theme: str) -> str:
    """Return the display label for ``theme``, or the raw key if it is unknown."""
    return THEME_LABELS.get(theme, theme)


def modality_label(modality: str) -> str:
    """Return the display label for ``modality``, or the raw key if it is unknown."""
    return MODALITY_LABELS.get(modality, modality)


def series_label(theme: str, domain: str) -> str:
    """Return the end-of-line label for one Panel B series.

    Falls back to the theme label plus a domain suffix for any series the figure
    has no hand-wrapped label for, so an unexpected domain still draws.
    """
    known = SERIES_END_LABELS.get((theme, domain))
    if known is not None:
        return known
    base = theme_label(theme).replace("\n", " ")
    return base + DOMAIN_SUFFIX.get(domain, f" ({domain})")
