"""PartStash — turn messy Taobao / JLCPCB purchase orders into a searchable
electronic-component inventory.

The package is split into three import-safe modules (no Streamlit, no global state)
so the data logic can be unit-tested in isolation from the UI:

* :mod:`partstash.core`     — parsing, column inference, table extraction, schema.
* :mod:`partstash.classify` — electronic / mechanical classification and search.
* :mod:`partstash.store`    — CSV persistence (load / save / upsert).

The Streamlit dashboard in ``app.py`` is a thin presentation layer on top of these.
"""

__version__ = "0.2.0"

__all__ = ["__version__"]
