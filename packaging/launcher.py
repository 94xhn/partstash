"""PyInstaller entry point.

Bundling Streamlit into a single ``.exe`` is awkward because Streamlit expects to be
launched via its own CLI. This launcher finds a free port, points
``COMPONENTS_STORE_PATH`` at a CSV next to the executable, and hands control to the
Streamlit CLI as if the user had run ``streamlit run app.py``.

Build with::

    pyinstaller packaging/ComponentsInventoryApp.spec
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import streamlit.web.cli as stcli


def resource_path(name: str) -> Path:
    """Resolve a bundled data file both when frozen and when run from source."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / name


def find_port() -> int:
    """Return the first free port from a small candidate list (8501 as fallback)."""
    for p in (3000, 3001, 3002, 3003, 8501):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return 8501


def main() -> int:
    app_file = resource_path("app.py")
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
    else:
        exe_dir = Path(__file__).resolve().parent.parent

    os.environ.setdefault("COMPONENTS_STORE_PATH", str(exe_dir / "inventory_store.csv"))
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.chdir(exe_dir)

    port = find_port()
    sys.argv = [
        "streamlit", "run", str(app_file),
        "--server.headless", "false",
        "--server.address", "127.0.0.1",
        "--server.port", str(port),
        "--global.developmentMode", "false",
        "--browser.gatherUsageStats", "false",
    ]
    return stcli.main()


if __name__ == "__main__":
    raise SystemExit(main())
