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
* Panel B's colour marks the **clinical domain** a theme's papers were pursued
  in, which is a modality statement and so is semantic. Theme is carried by the
  dash pattern instead, and marker doubles the domain so that greyscale keeps
  both dimensions. A series drawn undivided makes no domain claim and takes ink
  neutrals -- digital twins and agentic AI -- unless its papers state one
  anyway; see :data:`SERIES_DOMAIN_OVERRIDES`.

Colour is never the sole cue (guide S7). Every Panel B series keeps its own dash
pattern and a label at the end of the line, and within one plot the dash and
marker together separate every series with no help from hue, so the panel
survives a monochrome print. Panel A is legible with no colour at all: the
matrix, the block order and the bar heights carry the content.

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

#: Every theme key, in canonical order. Kept equal to ``aggregate.THEME_KEYS``
#: by a test in ``tests/test_classify.py``.
THEME_ORDER: Final[tuple[str, ...]] = (
    "foundation_models",
    "multimodal_integration",
    "digital_twins",
    "clinical_fda",
    "virtual_staining",
    "agentic_ai",
)

#: The themes Panel A draws as blocks, left to right. This is deliberately NOT
#: :data:`THEME_ORDER`. ``virtual_staining`` and ``agentic_ai`` were added to
#: Panel B only: at thirteen columns per block a fifth block puts the column
#: width below :data:`panel_a.MIN_COLUMN_WIDTH_IN`, which is the floor that holds
#: a dot legible, and ``tests/test_plot.py`` fails if it is breached. Author's
#: decision of 2026-09-02, and the same arithmetic rules out a sixth. A theme
#: added here must be added to the width test's arithmetic too.
PANEL_A_THEMES: Final[tuple[str, ...]] = (
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
    "virtual_staining": "Virtual Staining",
    "agentic_ai": "Agentic AI",
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
    "he_histology": "H&E Histology",
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
#: The four split values partition the theme: ``radiology`` means radiologic and
#: *not* pathologic, ``pathology`` the reverse, ``both`` is the cross-specialty
#: case, and ``none`` is a paper whose only labels are non-imaging. So
#: ``radiology + pathology + both + none == all``, and ``radiology + pathology``
#: alone does not reach the theme total. The figure displays ``both`` as
#: "cross-specialty"; the stored value stays ``both`` so this table and
#: ``paper_labels.csv`` agree.
DOMAIN_VALUES: Final[frozenset[str]] = frozenset(
    {"all", "radiology", "pathology", "both", "none"}
)

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

#: Legend entries for Panel A's dot colours, in matrix row order: one per hue in
#: :data:`MODALITY_COLORS`, named as in the style guide's modality table. Report
#: rows are green because they are clinical text, which is why "Clinical text /
#: EHR" covers Pathology Report and Radiology Report as well as Clinical / EHR Data.
MODALITY_GROUPS: Final[tuple[tuple[str, str], ...]] = (
    ("Digital pathology", DIGITAL_PATHOLOGY),
    ("Radiology imaging", RADIOLOGY_IMAGING),
    ("Clinical text / EHR", CLINICAL_TEXT),
    ("Molecular / omics", MOLECULAR),
)

#: Colour per clinical domain. This is the whole of Panel B's colour scheme:
#: colour marks the **domain** a theme's papers were pursued in, which is
#: semantic under the style guide, and every hue here is one of the project's
#: fixed assignments. Cross-specialty takes the guide's structural/integrative
#: grey, which it reserves for "fusion modules, joint models" -- a paper pairing
#: a radiologic with a pathologic modality is exactly that.
#:
#: Pathology is the deep variant, not the border hue. Every mark in Panel B is a
#: 1.3 pt stroke or 7 pt type, and the specification's own parenthetical assigns
#: the deep variant to thin strokes and labels. Panel A's dots keep the border
#: hue: they are filled marks, and they measured clear of the absent-dot neutral.
DOMAIN_COLORS: Final[dict[str, str]] = {
    "radiology": RADIOLOGY_IMAGING,
    "pathology": DIGITAL_PATHOLOGY_DEEP,
    "both": STRUCTURAL,
    "agentic": STRUCTURAL,
    "all": INK,
}

#: The domain an undivided series is *drawn* as, where it has one anyway.
#:
#: Virtual staining is drawn as a single line because splitting it would say
#: nothing: 75 of its 76 papers are pathologic and none is radiologic. But that
#: is itself a statement about its domain, and both of the domain channels --
#: hue and marker -- should make it. Drawing it as domain-less would throw away
#: the one semantic fact the series has, and would put it in the same ink as
#: digital twins, which it crosses in 2024-2025.
#:
#: Digital twins is genuinely domain-less and is not overridden: 22 radiology,
#: 7 pathology, 3 cross-specialty and 24 carrying no imaging modality at all.
#:
#: Agentic AI is not overridden either, and for a stronger reason than digital
#: twins': it is cross-cutting by definition. An agent that reads reports,
#: images and records is not usefully assigned to one specialty, which is why
#: the specification draws it undivided in the first place. Overriding it to
#: ``both`` -- the cross-specialty appearance, which is the tempting reading of
#: "cross-cutting" -- would be false in the sense ``both`` carries here: ``both``
#: means one paper carrying a radiologic *and* a pathologic modality, and it is
#: a claim about the papers, not about the theme's spirit. It would also put a
#: triangle and a diamond in one plot, which is the pair the measurement below
#: says is indistinguishable. Two reasons, either one sufficient.
#:
#: One override drives colour and marker together, so the two channels can never
#: contradict each other. The specification's table says "no domain split
#: (digital twins) | ink neutrals"; it names digital twins, and this reads that
#: parenthetical as the example it is rather than as the whole rule. Author
#: confirmed 2026-09-02.
#: ``agentic_ai`` is the second exception, added 2026-09-03 at the author's
#: request: it and digital twins are both undivided, so both drew as ink
#: diamonds and were told apart by dash alone. The style guide settles the
#: colour rather than leaving it to taste -- its structural/integrative row
#: names "fusion modules, joint models, **agents**", so ``STRUCTURAL`` is the
#: semantically correct hue for this theme, not merely a free one.
#:
#: The marker was chosen by measurement, not by eye. Rendering each candidate at
#: its drawn size and measuring the ink inside its bounding box: diamond 0.523,
#: triangle-down 0.528, thin diamond 0.519 -- all indistinguishable from the
#: diamond at 1 mm. Circle is 0.761 and hexagon 0.770, so hexagon would have
#: collided with the radiology circle already in that plot. "X" measures 0.706,
#: a 0.183 separation from the diamond, with a silhouette no round or
#: flat-sided marker resembles.
SERIES_DOMAIN_OVERRIDES: Final[dict[tuple[str, str], str]] = {
    ("virtual_staining", "all"): "pathology",
    ("agentic_ai", "all"): "agentic",
}

#: Dash pattern per theme. Under the 2026-09-02 specification, **theme is
#: carried by dash and marker, never by hue**, so two blue lines in the upper
#: plot are radiology work in two different themes. Every pattern must stay
#: distinguishable from every other at 1.3 pt: these are checked by a test.
THEME_DASHES: Final[dict[str, tuple]] = {
    "foundation_models": (0, ()),
    "multimodal_integration": (0, (6, 1.6)),
    "digital_twins": (0, (1, 1.5)),
    "clinical_fda": (0, (5, 1.2, 1, 1.2)),
    "virtual_staining": (0, (3.4, 1.5)),
    # Agentic AI shares the lower plot with all four of the above, and shares
    # ink and marker with digital twins, so its dash is the whole of what tells
    # the two apart. It is therefore chosen against its neighbours rather than
    # merely being unused: an even dash, dash and gap within 10% of each other,
    # where virtual staining's dash runs 2.3 times its gap, clinical's carries a
    # dot, and digital twins' is a fine dot. It is also the only pattern in the
    # lower plot whose texture survives being drawn flat along zero, which is
    # where nine of Agentic AI's twelve years sit.
    "agentic_ai": (0, (2.2, 2.0)),
}

#: Marker per clinical domain -- the *second* domain channel, and the one that
#: survives greyscale.
#:
#: Dash and marker were both spent on theme until 2026-09-02, which left hue as
#: the only domain cue, so a greyscale print lost the domain entirely: the three
#: domain lines of one theme were the same stroke in three near-identical greys
#: (luminance 87, 100 and 75). Splitting the channels costs nothing -- hue and
#: marker agree in colour, and in greyscale the dash still says which theme
#: while the marker now says which side. That satisfies the style guide's
#: "colour is never the sole cue" properly, instead of leaning on the end labels
#: as the only surviving cue.
#:
#: Four shapes that stay separable at 2.9 pt: circle, square, triangle, diamond.
#: Square and diamond are the risk pair and they do co-occur, in the lower plot.
#:
#: **Two series may share a marker, and two now do in each plot.** The marker
#: states a domain, not a theme, so every series making the same domain claim
#: draws the same shape and the dash separates them. Virtual staining and
#: clinical pathology have both been drawn as deep-pink squares since
#: 2026-09-02; digital twins and agentic AI are both diamonds from 2026-09-03.
#: Giving the second domain-less series a neutral shape of its own was
#: considered and measured, and the measurement argued against it:
#:
#: * By ink fill at 2.9 pt: square 1.000, circle 0.762, diamond 0.500. The
#:   tightest pair already drawn together in the lower plot is circle against
#:   square, 0.238 apart. **No unused marker clears 0.238 against all three.**
#:   The best is the star at 0.317, which is 0.183 from the diamond -- and its
#:   limbs measure 0.19 mm on the page, under the style guide's minimum stroke.
#:   Plus 0.556 and x 0.625 sit 0.056 and 0.125 from the diamond; hexagon 0.720
#:   sits 0.042 from the circle. Every candidate is a closer call than the pair
#:   the panel already tolerates.
#: * Ink fill is not the whole silhouette, so overlap was measured too, as
#:   intersection over union with the shapes centred as drawn. Circle against
#:   diamond is 0.77 and circle against square 0.79 -- the markers the lower plot
#:   already draws together overlap by three quarters. At 1.02 mm the marker is
#:   a weak channel for every series on the panel, which is why dash and the
#:   direct end labels were made to carry the identification in the first place.
#:
#: So a fifth shape would buy little, and would cost the rule that makes the
#: scheme legible: that a shape means a domain and nothing else. Author's call
#: is welcome to reverse this; it is one entry in this table.
DOMAIN_MARKERS: Final[dict[str, str]] = {
    "radiology": "o",
    "pathology": "s",
    "both": "^",
    "agentic": "X",
    "all": "D",
}

#: How a domain is named on the figure. ``both`` is displayed as
#: "cross-specialty"; the stored value stays ``both``.
DOMAIN_LABELS: Final[dict[str, str]] = {
    "all": "",
    "radiology": "radiology",
    "pathology": "pathology",
    "both": "cross-specialty",
    "none": "no domain",
}

#: End-of-line label for each Panel B series, hand-wrapped to fit the right
#: margin. Panel B labels its lines directly instead of using a legend box, so
#: these must stay short enough that six of them stack beside the upper plot
#: without colliding -- which is what sets Panel B's height. The widest line
#: here, "FDA Approval (pathology)", measures about 1.25 in at 7 pt against a
#: 1.49 in margin; a longer one would need the margin widened, not the type
#: shrunk. :func:`series_label` falls back to composing one for any series not
#: listed, so an unexpected domain still draws.
SERIES_END_LABELS: Final[dict[tuple[str, str], str]] = {
    ("foundation_models", "radiology"): "Foundation Models\n(radiology)",
    ("foundation_models", "pathology"): "Foundation Models\n(pathology)",
    ("foundation_models", "both"): "Foundation Models\n(cross-specialty)",
    ("multimodal_integration", "radiology"): "Multimodal Integration\n(radiology)",
    ("multimodal_integration", "pathology"): "Multimodal Integration\n(pathology)",
    ("multimodal_integration", "both"): "Multimodal Integration\n(cross-specialty)",
    ("digital_twins", "all"): "Digital Twins",
    ("virtual_staining", "all"): "Virtual Staining",
    ("agentic_ai", "all"): "Agentic AI",
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


def domain_color(domain: str) -> str:
    """Return the semantic colour of one clinical domain."""
    return DOMAIN_COLORS.get(domain, INK)


def appearance_domain(theme: str, domain: str) -> str:
    """Return the domain a series is drawn as.

    Usually the domain itself. See :data:`SERIES_DOMAIN_OVERRIDES` for the one
    series that is drawn undivided but still has a domain worth stating.
    """
    return SERIES_DOMAIN_OVERRIDES.get((theme, domain), domain)


def series_color(theme: str, domain: str) -> str:
    """Return the line colour for one Panel B series. Colour marks the domain."""
    return domain_color(appearance_domain(theme, domain))


def series_text_color(theme: str, domain: str) -> str:
    """Return the end-of-line label colour for one Panel B series.

    The same colour as the line: every hue in :data:`DOMAIN_COLORS` is already
    the deep variant or a neutral, so all of them read at 7 pt.
    """
    return series_color(theme, domain)


def series_dash(theme: str, domain: str) -> tuple:
    """Return the dash pattern for one Panel B series.

    Dash marks the theme, so this ignores ``domain``: the three domain lines of
    one theme share a pattern and are told apart by hue and by their end labels.
    """
    return THEME_DASHES.get(theme, (0, ()))


def series_marker(theme: str, domain: str) -> str:
    """Return the marker for one Panel B series.

    Marker marks the **domain**, as hue does, so that greyscale keeps both
    dimensions: dash says which theme, marker says which side. Hue and marker
    are driven by the same :func:`appearance_domain` and cannot disagree.
    """
    return DOMAIN_MARKERS.get(appearance_domain(theme, domain), "o")


def theme_label(theme: str) -> str:
    """Return the display label for ``theme``, or the raw key if it is unknown."""
    return THEME_LABELS.get(theme, theme)


def modality_label(modality: str) -> str:
    """Return the display label for ``modality``, or the raw key if it is unknown."""
    return MODALITY_LABELS.get(modality, modality)


def series_label(theme: str, domain: str) -> str:
    """Return the end-of-line label for one Panel B series.

    Falls back to composing one from the theme label and the domain name for any
    series the figure has no hand-wrapped label for, so an unexpected domain
    still draws rather than going out unlabelled.
    """
    known = SERIES_END_LABELS.get((theme, domain))
    if known is not None:
        return known
    base = theme_label(theme).replace("\n", " ")
    named = DOMAIN_LABELS.get(domain, domain)
    return base if not named else f"{base}\n({named})"
