"""Composition of the two sibling figures onto one four-panel canvas.

The manuscript is capped at five figures and tables combined, and the literature
figure and the clinical-operations figure were spending two of them. This package
draws both onto one canvas so they cost one float instead of two.

It holds **no drawing code and no data**. Every mark comes from a panel function
in ``trends.plotting`` or ``clinops.plotting``, and every number comes from those
projects' own ``data/processed`` directories, read through their own validators.
This package contributes exactly two things: the geometry that says where the
four panels go, and the panel letters A-D that renumber them.

That is deliberate. A merged figure that re-implemented either panel would be a
third thing to keep in step with two pipelines, and the first divergence would be
silent -- a published number that no longer matches the table it came from. Here
a change to either sibling reaches this figure on the next build, because there is
nothing in between.

One command line: ``python -m combined.plot --help``.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
