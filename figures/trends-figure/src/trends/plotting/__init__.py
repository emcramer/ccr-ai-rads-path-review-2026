"""Figure construction for the CCR trends figure.

The subpackage is deliberately thin and side-effect free. Modules:

* ``style``     -- canonical keys, display labels, colours, dash patterns, rcParams.
* ``io``        -- read and validate the three processed tables.
* ``panel_a``   -- the inverted UpSet panel (modality combinations per theme).
* ``panel_b``   -- the theme-volume-over-time panel.
* ``synthetic`` -- generator for the synthetic stand-in corpus used before real data.

``trends.plot`` is the command line entry point that assembles the panels.
Nothing here classifies, filters, or recounts the corpus; it draws what it is given.
"""

__all__ = ["style", "io", "panel_a", "panel_b", "synthetic"]
