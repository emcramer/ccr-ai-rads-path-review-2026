"""Clinical-operations pipeline: FDA AI device authorizations, by oncology domain.

The package turns two public sources into the three tables the figure is drawn
from, with full provenance. Five steps, five modules:

* ``config``    -- load and validate ``source.yaml`` and ``oncology_codes.yaml``.
* ``fetch``     -- download the FDA device list and the openFDA classification
                   records, write a dated append-only snapshot and a manifest.
* ``enrich``    -- join each device row to its product code's classification.
* ``classify``  -- apply the oncology rule in ``oncology_codes.yaml``.
* ``aggregate`` -- reduce the labelled devices to the figure's input tables.

Every module is a command line: ``python -m clinops.<module> --help``.

Nothing here is stochastic. The same snapshot and the same configuration give
the same tables, always, which is why the snapshot is kept rather than the URL.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
