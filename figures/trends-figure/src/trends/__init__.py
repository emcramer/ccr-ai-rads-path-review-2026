"""Retrieval and parsing pipeline for the CCR trends figure.

The package turns the PubMed query in ``config/corpus.yaml`` into a parsed
record table with full provenance. Three steps, three modules:

* ``config``  -- load and validate the YAML search configuration.
* ``pubmed``  -- query E-utilities, save every response, write a manifest.
* ``parse``   -- turn the saved XML into one row per record.

``fetch`` is the command line entry point that runs all three.

The ``plotting`` subpackage draws the figure from the parsed records and is
documented in its own module.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
