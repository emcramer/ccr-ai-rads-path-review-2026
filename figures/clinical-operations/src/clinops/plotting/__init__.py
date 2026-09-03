"""Figure construction for the clinical-operations figure.

The subpackage is deliberately thin and side-effect free apart from the font
registration it inherits from ``trends.plotting.style``. Modules:

* ``io``      -- read and validate the three processed tables.
* ``panel_a`` -- cumulative authorizations over time, log y axis.
* ``panel_b`` -- authorization pathway composition by domain.

``clinops.plot`` is the command line entry point that assembles the panels.
Nothing here classifies, filters, or recounts the snapshot; it draws what it is
given.

This module itself holds the figure's **canonical key vocabulary and its
appearance table**, which is the "Canonical keys" section of
``docs/figure-spec.md`` compiled into Python, the same relationship
``trends.plotting.style`` has to its own spec. Both panels and ``io`` read the
vocabulary from here, so a key exists in exactly one place.

Style is imported, never re-declared
------------------------------------
Every colour, type size and rcParam comes from ``trends.plotting.style``, which
is ``../../ink_style_guide.md`` compiled into Python and is the authority for
this figure too (``../../AGENTS.md``, "Route A"). This project is installed
against it with ``pip install -e ../trends-figure``. **No token is redefined
here.** What this module adds is only the *assignment* of already-defined tokens
to this figure's own keys, plus the dash, marker and hatch patterns that carry
the non-modality distinctions.

Colour is semantic and nothing else (guide S1, S3):

* Hue marks the **clinical domain**, which is a data-modality statement:
  radiology ``style.RADIOLOGY_IMAGING``, pathology ``style.DIGITAL_PATHOLOGY``.
  Those two assignments are fixed project-wide and are not this figure's to
  rearrange.
* The two radiology categories therefore **share a hue**, because they are the
  same modality. Cancer detection and radiation therapy are separated by dash
  pattern, by marker, and by a direct end-of-line label instead. Tinting one of
  them differently would be decoration, and would claim a modality difference
  that does not exist.
* The **marketing pathway is not a modality at all**, so it gets no hue. It is
  carried by fill texture -- solid, diagonal hatch, cross hatch -- which is what
  the guide asks for before a new hue is even proposed (guide S3).

Colour is never the sole cue (guide S7). Panel A's three lines are separable by
dash and marker alone and each carries its own label; Panel B's three pathways
are separable by texture alone and each carries its own key entry and its own
printed count. Both panels survive a greyscale print with nothing lost.

Deep versus border hue
----------------------
The guide assigns the deep variant to small type and thin strokes and the border
hue to areas. So Panel A's 1.3 pt lines and 5.8 pt gutter labels take
``*_DEEP`` where the guide's own parenthetical calls for it -- pathology pink,
which goes pale at that weight -- while Panel B's bar fills, which are areas,
take the border hues. Radiology blue is dark enough at 1.3 pt to stay on the
border hue, exactly as the sibling trends figure draws it.
"""

from __future__ import annotations

from typing import Final

from trends.plotting import style

__all__ = ["io", "panel_a", "panel_b"]

# --------------------------------------------------------------------------
# Canonical keys. See the "Canonical keys" section of docs/figure-spec.md.
# --------------------------------------------------------------------------

#: Every category key, in figure order: the two radiology categories, then
#: pathology. Radiation therapy is a separate category rather than being merged
#: into radiology, for the reason recorded in ``config/oncology_codes.yaml``:
#: those 79 devices automate contouring and dose planning rather than
#: interpreting an image for a diagnosis, pathology has no analogue, and folding
#: them in would inflate the radiology side of a diagnostic comparison. Keeping
#: them apart lets both the 145-vs-9 and the 66-vs-9 comparison be read off
#: Panel A.
CATEGORY_ORDER: Final[tuple[str, ...]] = (
    "radiology_cancer_detection",
    "radiology_radiation_therapy",
    "pathology",
)

#: Permitted values of the ``domain`` column, in figure order.
DOMAIN_ORDER: Final[tuple[str, ...]] = ("radiology", "pathology")

#: The domain each category belongs to. The ``domain`` column of every input
#: table is checked against this rather than merely against the vocabulary, so a
#: row claiming a pathology category is radiological fails the schema.
CATEGORY_DOMAIN: Final[dict[str, str]] = {
    "radiology_cancer_detection": "radiology",
    "radiology_radiation_therapy": "radiology",
    "pathology": "pathology",
}

#: FDA marketing pathways, in figure order: the routine one first, then the two
#: that create or amend a device category. Read by the upstream pipeline from
#: the submission-number prefix (``K``, ``DEN``, ``P``); the figure trusts the
#: column and never parses a submission number itself.
PATHWAY_ORDER: Final[tuple[str, ...]] = ("510(k)", "De Novo", "PMA")

#: Display label for each category. Sentence case, because everything inside a
#: panel is sentence case (guide S6); only the panel titles are Title Case.
CATEGORY_LABELS: Final[dict[str, str]] = {
    "radiology_cancer_detection": "Detection and assessment",
    "radiology_radiation_therapy": "Treatment planning",
    "pathology": "Digital pathology",
}

#: Display label for each domain, used on Panel B's bars.
DOMAIN_LABELS: Final[dict[str, str]] = {
    "radiology": "Radiology",
    "pathology": "Pathology",
}

#: End-of-line label for each Panel A series, hand-wrapped to fit the right
#: gutter. Panel A labels its lines directly instead of using a legend box, so
#: these must stay short enough to stack beside the nine device labels without
#: colliding -- which, with the device labels, is what sets the figure's width.
#: The widest line here, "assessment (radiology)", measures about 0.95 in at 7 pt
#: against a 1.53 in gutter; a longer one would need the gutter widened, not the
#: type shrunk. :func:`series_label` composes one for any category not listed,
#: so an unexpected category still draws rather than going out unlabelled.
SERIES_END_LABELS: Final[dict[str, str]] = {
    "radiology_cancer_detection": "Detection and\nassessment (radiology)",
    "radiology_radiation_therapy": "Treatment planning\n(radiology)",
    "pathology": "Digital pathology",
}

# --------------------------------------------------------------------------
# Appearance. Every value below is a token imported from ``style``, or a dash,
# marker or hatch -- the non-hue channels the guide names.
# --------------------------------------------------------------------------

#: Line and label colour per category. Hue marks the domain, so the two
#: radiology categories share one. Pathology takes the deep variant: every
#: pathology mark in Panel A is a 1.3 pt stroke, a 2.9 pt marker or 5.8 pt type,
#: and the guide assigns the deep variant to exactly those. Radiology stays on
#: the border hue, as the sibling trends figure draws it.
CATEGORY_COLORS: Final[dict[str, str]] = {
    "radiology_cancer_detection": style.RADIOLOGY_IMAGING,
    "radiology_radiation_therapy": style.RADIOLOGY_IMAGING,
    "pathology": style.DIGITAL_PATHOLOGY_DEEP,
}

#: Area fill per domain, for Panel B's bars. Areas take the border hues.
DOMAIN_COLORS: Final[dict[str, str]] = {
    "radiology": style.RADIOLOGY_IMAGING,
    "pathology": style.DIGITAL_PATHOLOGY,
}

#: Hatch-line and small-type colour per domain, for Panel B. Hatch lines are
#: 0.45 pt and segment counts are 5.5 pt, so both are the guide's "small type
#: and thin stroke" case and take the deep variants.
DOMAIN_COLORS_DEEP: Final[dict[str, str]] = {
    "radiology": style.RADIOLOGY_IMAGING_DEEP,
    "pathology": style.DIGITAL_PATHOLOGY_DEEP,
}

#: Dash pattern per category -- the channel that separates the two radiology
#: series, which share a hue by rule. The three patterns must stay
#: distinguishable from each other at 1.3 pt: a solid line, a long even dash
#: whose dash runs nearly four times its gap, and a dash-dot, which is the same
#: three-way separation the sibling figure uses for its densest plot.
CATEGORY_DASHES: Final[dict[str, tuple]] = {
    "radiology_cancer_detection": (0, ()),
    "radiology_radiation_therapy": (0, (6, 1.6)),
    "pathology": (0, (5, 1.2, 1, 1.2)),
}

#: Marker per category -- the second non-hue channel, and the one that survives
#: greyscale at a glance. Circle, triangle and square are three of the four
#: shapes the sibling figure measured as separable at this size; the risk pair
#: it identified (square against diamond) does not occur here because no series
#: draws a diamond.
CATEGORY_MARKERS: Final[dict[str, str]] = {
    "radiology_cancer_detection": "o",
    "radiology_radiation_therapy": "^",
    "pathology": "s",
}

#: Fill texture per marketing pathway. **Pathway is not a modality**, so under
#: the guide it may not have a hue; texture is what the guide names in its
#: place. 510(k) is the unmarked, routine case and draws solid; the two pathways
#: that create or amend a device category draw hatched, and the harder route
#: draws the denser texture. Two distinct hatch angles plus solid stay separable
#: in greyscale and at 300 dpi, and each carries a key entry and a printed count
#: besides.
PATHWAY_HATCH: Final[dict[str, str]] = {
    "510(k)": "",
    "De Novo": "///",
    "PMA": "xxx",
}

#: Display label for each pathway. These are FDA's own names for the routes and
#: are not sentence-cased.
PATHWAY_LABELS: Final[dict[str, str]] = {
    "510(k)": "510(k)",
    "De Novo": "De Novo",
    "PMA": "PMA",
}

#: Gutter label for each pathology device, keyed by submission number and
#: hand-wrapped. Year plus device name, four words or fewer, per the guide's
#: content rules: these name what the element *is* and explain nothing. FDA's
#: own ``device`` strings are longer than the gutter ("AUTOPAP 300 QC Automatic
#: Pap Screener", "INFINITT Digital Pathology Solution"), so the display name is
#: shortened to the name the field actually uses.
#:
#: :func:`device_label` falls back to wrapping the raw ``device`` field for any
#: submission not listed, so a device added by a later snapshot still draws --
#: wider than the gutter, which is visible, rather than absent, which is not.
DEVICE_LABELS: Final[dict[str, str]] = {
    "P940029": "1995  PAPNET Testing System",
    "P950009": "1995  AUTOPAP 300 QC",
    "DEN200080": "2021  Paige Prostate",
    "P210011": "2023  Tempus xT CDx",
    "DEN210035": "2024  Genius Digital\n           Diagnostics",
    "K241232": "2025  Galen Second Read",
    "DEN240068": "2025  ArteraAI Prostate",
    "K250003": "2025  GENESEEQPRIME",
    "K243449": "2025  INFINITT DPS",
}


def category_label(category: str) -> str:
    """Return the display label for ``category``, or the raw key if unknown."""
    return CATEGORY_LABELS.get(category, category)


def domain_label(domain: str) -> str:
    """Return the display label for ``domain``, or the raw key if unknown."""
    return DOMAIN_LABELS.get(domain, domain)


def series_label(category: str) -> str:
    """Return the end-of-line label for one Panel A series.

    Falls back to the category's display label, so a category the figure has no
    hand-wrapped label for still draws rather than going out unlabelled.
    """
    return SERIES_END_LABELS.get(category, category_label(category))


def category_color(category: str) -> str:
    """Return the line and label colour for one category.

    Falls back to the guide's structural grey, which is what it assigns to
    anything that is not one of the four named data modalities.
    """
    return CATEGORY_COLORS.get(category, style.STRUCTURAL)


def domain_color(domain: str, *, deep: bool = False) -> str:
    """Return the fill (or, with ``deep``, the thin-stroke) colour of a domain."""
    table = DOMAIN_COLORS_DEEP if deep else DOMAIN_COLORS
    return table.get(domain, style.STRUCTURAL)


def category_dash(category: str) -> tuple:
    """Return the dash pattern for one Panel A series."""
    return CATEGORY_DASHES.get(category, (0, ()))


def category_marker(category: str) -> str:
    """Return the marker for one Panel A series."""
    return CATEGORY_MARKERS.get(category, "o")


def pathway_hatch(pathway: str) -> str:
    """Return the hatch pattern for one marketing pathway; "" means solid."""
    return PATHWAY_HATCH.get(pathway, "")


def pathway_label(pathway: str) -> str:
    """Return the display label for ``pathway``, or the raw key if unknown."""
    return PATHWAY_LABELS.get(pathway, pathway)


def device_label(submission_number: str, device: str, year: int) -> str:
    """Return the gutter label for one pathology device.

    Args:
        submission_number: FDA submission number, the key of
            :data:`DEVICE_LABELS`.
        device: FDA's own device name, used only when there is no hand-wrapped
            label for this submission.
        year: Decision year, prefixed to the fallback label.

    Returns:
        A short label of the form ``"YEAR  Device name"``. The fallback keeps
        the first four words of FDA's name, which is the guide's limit for a
        functional label in artwork.
    """
    known = DEVICE_LABELS.get(submission_number)
    if known is not None:
        return known
    words = str(device).split()
    return f"{year}  " + " ".join(words[:4])
