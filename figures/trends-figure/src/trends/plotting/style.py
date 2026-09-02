"""Canonical keys, labels, and visual style for the trends figure.

Every key and every display label in this module comes from the "Canonical keys"
section of ``docs/figure-spec.md``. They are repeated here, rather than imported
from ``trends.config``, because the plotting code is required to depend on
nothing but the three processed tables. If the retrieval package later exposes
the same registry, the two should be reconciled and one of them deleted.

Colour and type
---------------
Both follow ``../ink_style_guide.md``, the project style guide.

**Colour is semantic, never decorative** (guide S1, S3). It appears only where it
identifies a data modality, and the modality-to-hue assignments are fixed
project-wide. So:

* Panel A's matrix dots carry their row's modality colour; everything structural
  in the panel -- connectors, bars, rules, bands -- is drawn in ink and line
  greys. A bar is a *combination* of modalities, not one modality, so it carries
  no modality colour.
* Panel B's foundation-models, multimodal-integration and digital-twins series
  are themes, not modalities, so they are drawn in ink/greys and told apart by
  dash pattern and marker. The two clinical lines *are* modality-domain series --
  radiology against pathology -- so they take the radiology and pathology hues.
  That is the only place in Panel B where colour means something.

Colour is never the sole cue (guide S7). Every Panel B series keeps its own dash
pattern, its own marker, and a label at the end of the line, and Panel A is
legible with no colour at all: the matrix, the block order and the bar heights
carry the content.

**Type** is IBM Plex Serif for panel letters and theme titles, IBM Plex Sans for
everything else. The faces are vendored under ``assets/fonts/`` and registered
with matplotlib at import time by :func:`register_fonts`, which raises rather
than let matplotlib substitute a face silently. See :data:`FS_PANEL_LETTER` and
the note above it for why the guide's sizes are not scaled literally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from matplotlib import font_manager

# --------------------------------------------------------------------------
# Fonts
#
# The two families the style guide names are vendored under ``assets/fonts/``
# rather than installed system-wide, so nothing about the build depends on the
# machine it runs on. They are registered with matplotlib when this module is
# imported, before any artist exists.
#
# A missing face raises. The guide is explicit that substitution must not be
# silent, and matplotlib's default behaviour is exactly that: it warns once, at
# a log level nobody reads, and renders the whole figure in DejaVu Sans. A
# figure that is wrong in a way nobody notices is the failure this project keeps
# guarding against.
# --------------------------------------------------------------------------

#: Directory name, relative to a project or package root, holding the faces.
_FONT_SUBDIR: Final[tuple[str, str]] = ("assets", "fonts")

#: Family name that matplotlib reports for each vendored file, and the file
#: itself. Both families need all four faces: regular for body text, bold for
#: panel letters and titles, italic for axis titles, bold-italic for
#: completeness, so a caller asking for one never falls through to a synthesised
#: oblique.
FONT_FILES: Final[dict[tuple[str, str, str], str]] = {
    ("IBM Plex Sans", "normal", "normal"): "IBMPlexSans-Regular.ttf",
    ("IBM Plex Sans", "bold", "normal"): "IBMPlexSans-Bold.ttf",
    ("IBM Plex Sans", "normal", "italic"): "IBMPlexSans-Italic.ttf",
    ("IBM Plex Sans", "bold", "italic"): "IBMPlexSans-BoldItalic.ttf",
    ("IBM Plex Serif", "normal", "normal"): "IBMPlexSerif-Regular.ttf",
    ("IBM Plex Serif", "bold", "normal"): "IBMPlexSerif-Bold.ttf",
    ("IBM Plex Serif", "normal", "italic"): "IBMPlexSerif-Italic.ttf",
    ("IBM Plex Serif", "bold", "italic"): "IBMPlexSerif-BoldItalic.ttf",
}

#: The sans family, for everything that is not a panel letter or a title.
SANS: Final[str] = "IBM Plex Sans"

#: The serif family, for panel letters and theme titles.
SERIF: Final[str] = "IBM Plex Serif"


class FontsUnavailable(RuntimeError):
    """A face named by the style guide is missing, or resolves to a substitute.

    Raised at import time. The figure is not drawn in a fallback face, because a
    fallback face is a silent substitution and the style guide forbids one.
    """


def font_dir() -> Path:
    """Return the directory holding the vendored faces.

    Resolved from this file's own location, walking up until ``assets/fonts``
    appears, so the answer does not depend on the working directory the build
    was launched from.

    Raises:
        FontsUnavailable: If no such directory exists above this module.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent.joinpath(*_FONT_SUBDIR)
        if candidate.is_dir():
            return candidate
    raise FontsUnavailable(
        f"no {'/'.join(_FONT_SUBDIR)} directory above {here}; the IBM Plex faces "
        "the style guide requires are vendored there and the figure will not be "
        "drawn in a substitute"
    )


def register_fonts() -> Path:
    """Register every vendored face with matplotlib and confirm each resolves.

    Returns:
        The directory the faces were loaded from.

    Raises:
        FontsUnavailable: If a file is missing, or if matplotlib still resolves
            one of the eight family/weight/style combinations to some other
            font once they are all registered.
    """
    directory = font_dir()
    missing = sorted(
        name for name in FONT_FILES.values() if not (directory / name).is_file()
    )
    if missing:
        raise FontsUnavailable(
            f"{directory}: missing font file(s) {', '.join(missing)}; install the "
            "IBM Plex families rather than letting matplotlib substitute"
        )
    for name in FONT_FILES.values():
        font_manager.fontManager.addfont(str(directory / name))

    substituted = []
    for (family, weight, style_), name in FONT_FILES.items():
        properties = font_manager.FontProperties(
            family=family, weight=weight, style=style_
        )
        resolved = Path(font_manager.findfont(properties)).resolve()
        if resolved != (directory / name).resolve():
            substituted.append(f"{family} {weight} {style_} -> {resolved.name}")
    if substituted:
        raise FontsUnavailable(
            "matplotlib substituted a face the style guide names: "
            + "; ".join(substituted)
        )
    return directory


#: Where the faces came from. Registration happens on import, so any module that
#: imports ``style`` can draw in IBM Plex without ordering its own setup call.
FONT_DIR: Final[Path] = register_fonts()

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

# Neutral inks, from the style guide's neutral table. Kept together so a journal
# illustrator can retune them in one place.
INK: Final[str] = "#141414"          # primary text, panel letters, theme titles
LINE: Final[str] = "#33373D"         # connectors and other structural strokes
SUBTLE: Final[str] = "#5C6068"       # axis titles, tick labels, small functional labels
BAR_FILL: Final[str] = "#3D4147"     # secondary output: Panel A's combination bars
STRUCTURAL: Final[str] = "#4B4B4B"   # the guide's structural/integrative accent

# Hatched fill for Panel A's remainder column: 45 degrees, white ground, hatch
# lines and border in the bars' own ink.
#
# DO NOT "correct" this back to the style guide's section 4 hatch (#F0F0F0
# ground, #BDBDBD lines). That specification exists for "masked, hidden, or
# inactive elements", and the remainder column is none of those. It is the rest
# of the distribution drawn at its true height: in the multimodal-integration
# block it is 45% of the theme and the tallest bar in the block. Drawn in the
# pale spec it became the faintest mark in the block where it should be the
# loudest -- precisely the misreading ``docs/DECISIONS.md`` warns against when it
# says not to let a redraw shrink the remainder into a rounding error. Author's
# decision of 2026-09-02, overruling the earlier instruction to apply section 4
# literally here.
#
# What the figure actually needs from the hatch is only that the column read as
# a different *kind* of quantity -- an aggregate, not one more combination --
# and hatching in the bar ink does that while keeping the visual weight the
# bar's height has earned. It still honours section 3's instruction to reach for
# hatching before inventing a new hue; it declines a spec written for a
# different purpose.
HATCH_GROUND: Final[str] = "#FFFFFF"
HATCH_LINE: Final[str] = "#3D4147"
HATCH_PATTERN: Final[str] = "////"

#: Semantic modality palette (Okabe-Ito; Wong, Nat Methods 2011). These five
#: assignments are FIXED project-wide by the style guide and must not be
#: rearranged to suit one figure.
RADIOLOGY_IMAGING: Final[str] = "#0072B2"
DIGITAL_PATHOLOGY: Final[str] = "#CC79A7"
CLINICAL_TEXT: Final[str] = "#009E73"
MOLECULAR: Final[str] = "#E69F00"

#: Deep variant of each modality hue, for small text. The border hues above are
#: sized for areas and strokes; at 7 pt on white they read light, and pink and
#: green go pale in greyscale. The deep variants are the guide's own, from the
#: second column of its modality table.
RADIOLOGY_IMAGING_DEEP: Final[str] = "#00517F"
DIGITAL_PATHOLOGY_DEEP: Final[str] = "#8F4B73"

#: Modality hue per matrix row. A present dot takes its row's colour, so colour
#: in Panel A always answers "what kind of data is this", never "which theme".
MODALITY_COLORS: Final[dict[str, str]] = {
    "he_histology": DIGITAL_PATHOLOGY,
    "ihc": DIGITAL_PATHOLOGY,
    "spatial_proteomics": DIGITAL_PATHOLOGY,
    "spatial_transcriptomics": DIGITAL_PATHOLOGY,
    "pathology_report": CLINICAL_TEXT,
    "mri": RADIOLOGY_IMAGING,
    "ct": RADIOLOGY_IMAGING,
    "pet": RADIOLOGY_IMAGING,
    "ultrasound": RADIOLOGY_IMAGING,
    "mammography": RADIOLOGY_IMAGING,
    "xray": RADIOLOGY_IMAGING,
    "radiology_report": CLINICAL_TEXT,
    "genomics": MOLECULAR,
    "clinical_data": CLINICAL_TEXT,
    "other": STRUCTURAL,
}

#: Colour per Panel B series. Three of the five series are *themes*, not
#: modalities, so under the guide they carry no hue at all and are told apart by
#: dash pattern and marker; they are drawn in the three neutral inks. The two
#: clinical lines are modality-domain series -- radiology against pathology --
#: so they take the fixed modality hues, and that comparison is the one the
#: review cares most about.
SERIES_COLORS: Final[dict[tuple[str, str], str]] = {
    ("foundation_models", "all"): INK,
    ("multimodal_integration", "all"): SUBTLE,
    ("digital_twins", "all"): LINE,
    ("clinical_fda", "radiology"): RADIOLOGY_IMAGING,
    # The deep pathology variant, not the border hue. Measured in greyscale,
    # #CC79A7 came out at luminance ~151 -- the lightest stroke on the page --
    # and it carries the pathology series, which is the review's argument. The
    # guide lists the deep variants for sub-labels and icon tint, and a 1.3 pt
    # line at this size is nearer those than a card border. Radiology stays on
    # #0072B2, which measures ~87 and needs no help.
    ("clinical_fda", "pathology"): DIGITAL_PATHOLOGY_DEEP,
}

#: End-of-line label colour per series: the line's own colour for the neutrals,
#: the deep variant for the two hued lines, which are set at 7 pt.
SERIES_TEXT_COLORS: Final[dict[tuple[str, str], str]] = {
    ("foundation_models", "all"): INK,
    ("multimodal_integration", "all"): SUBTLE,
    ("digital_twins", "all"): LINE,
    ("clinical_fda", "radiology"): RADIOLOGY_IMAGING_DEEP,
    ("clinical_fda", "pathology"): DIGITAL_PATHOLOGY_DEEP,
}

#: Dash pattern per Panel B series. Three series carry no colour at all, so dash
#: and marker are the whole of what tells them apart; the two clinical lines
#: differ by hue *and* by dash, as the specification requires.
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

# Further neutrals, below the guide's named five. These are lighter than
# anything the guide tabulates because they do work the guide's reference figure
# has no equivalent of: an absent-value dot, a row band, a hairline separator.
# Absent dots. Lightened from #D6D6D6 on 2026-09-02 to widen the greyscale
# margin under the genomics row: #E69F00 converts to luminance ~162, and against
# #D6D6D6 (~214) that was the narrowest present-versus-absent gap in the matrix.
# Lightening the neutral fixes it without touching a fixed modality assignment.
# It cannot go much further: these dots also sit on the #F2F2F2 row bands.
INK_LIGHT: Final[str] = "#E3E3E3"    # absent dots
BAND: Final[str] = "#F2F2F2"         # alternating matrix row bands
RULE: Final[str] = "#9A9A9A"         # block separators, axis spines
PARTIAL_BAND: Final[str] = "#E9E9E9"  # shading over the partial final year

# --------------------------------------------------------------------------
# Type sizes, in points
#
# The style guide's sizes are SVG user units on a canvas about 1355 units wide.
# This figure is 7.5 in, or 540 pt, wide, so scaling the guide literally means
# multiplying by 540/1355 = 0.40: body text would land near 5 pt and the guide's
# own 9.5-unit floor near 3.8 pt. Both are below print legibility, and below
# floors this project has already measured and tested -- the row-label gutter,
# the 12 pt matrix row pitch, and the 5.0 pt bar-value floor are all pinned by
# ``tests/test_plot.py``.
#
# So the guide's *hierarchy and proportions* are preserved and its absolute
# numbers are not. Sizes below are anchored on the tested floors at the bottom
# of the scale and stepped upward by the guide's own ratios:
#
#     small functional label   5.8 pt   anchor (the guide's 10-11 unit row)
#     axis title               7.5 pt   1.29x anchor (guide 13/10.5 = 1.24x)
#     section subtitle         8.6 pt   1.15x axis title (guide 15/13 = 1.15x)
#     panel letter            12.6 pt   1.47x subtitle (guide 22/15 = 1.47x)
#
# The panel letter is comfortably the largest type on the page, which is what
# the hierarchy is for. The guide's 18-unit "panel title" row has no counterpart
# here: this figure's panels carry a letter and no title.
# --------------------------------------------------------------------------

FS_PANEL_LETTER: Final[float] = 12.6
FS_THEME_TITLE: Final[float] = 8.6
FS_AXIS_LABEL: Final[float] = 7.5
# 7.5, not the 7.0 this figure carried under DejaVu Sans. IBM Plex Sans is the
# narrower face -- "Genomics / Transcriptomics" measures 1.29 in against DejaVu's
# 1.38 in at 7 pt -- so the row-label gutter gained room that the switch of face
# paid for. Spending it on the labels rather than banking it: at 7.5 the longest
# label needs 1.42 in of the 1.44 in gutter, which the gutter test still passes,
# and the matrix row pitch of 13.2 pt still clears its 1.7x floor.
FS_TICK: Final[float] = 7.5
FS_BAR_VALUE: Final[float] = 5.5
FS_NOTE: Final[float] = 5.8
FS_SERIES_LABEL: Final[float] = 7.0


def rc_params() -> dict:
    """Return the matplotlib rcParams the figure is drawn under.

    Fonts are embedded as TrueType (``fonttype`` 42) rather than as Type 3
    subsets, so the PDF stays editable by the journal's illustrator, and the SVG
    references them by name (``svg.fonttype`` "none") rather than outlining
    them, as the style guide's deliverables section requires.

    The fallback stacks are the guide's own, but nothing is expected to reach
    them: :func:`register_fonts` has already raised at import time if a face is
    missing, so a fallback here would mean a bug rather than a substitution.
    """
    return {
        "font.family": "sans-serif",
        "font.sans-serif": [SANS, "Arial", "Helvetica"],
        "font.serif": [SERIF, "Georgia"],
        "font.size": FS_TICK,
        "axes.linewidth": 0.6,
        "axes.edgecolor": RULE,
        "axes.labelcolor": SUBTLE,
        "text.color": INK,
        "xtick.color": SUBTLE,
        "ytick.color": SUBTLE,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.2,
        "ytick.major.size": 2.2,
        "lines.solid_capstyle": "round",
        # The remainder bar is hatched. The default hatch line is heavy enough at
        # 300 dpi to fill a narrow bar solid, which would hide that it is hollow.
        # 0.65 was needed only while the hatch was drawn in the style guide's
        # pale #BDBDBD. Back in the bar ink, that weight would fill a 0.10 in
        # column solid and hide that the bar is hollow at all.
        "hatch.linewidth": 0.45,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "figure.dpi": 100,
        "savefig.dpi": 300,
    }


def modality_color(modality: str) -> str:
    """Return the semantic colour of one modality row.

    Falls back to the structural grey, which is what the guide assigns to
    anything that is not one of the four named data modalities.
    """
    return MODALITY_COLORS.get(modality, STRUCTURAL)


def series_color(theme: str, domain: str) -> str:
    """Return the line colour for one Panel B series.

    Falls back to ink: an unexpected series is not a modality, so it gets no hue.
    """
    return SERIES_COLORS.get((theme, domain), INK)


def series_text_color(theme: str, domain: str) -> str:
    """Return the end-of-line label colour for one Panel B series."""
    return SERIES_TEXT_COLORS.get((theme, domain), series_color(theme, domain))


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
