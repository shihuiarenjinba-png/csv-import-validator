"""Writable, per-user paths for Data Contract Auditor."""
from __future__ import annotations

import os
import platform as platform_module
from pathlib import Path
from typing import Mapping


APP_DATA_DIRECTORY = "DataContractAuditor"
RESULTS_DIRECTORY = "Results"


def default_results_directory(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    system: str | None = None,
) -> Path:
    """Return a user-writable location without relying on the process CWD.

    MSIX package locations and the current working directory may be read-only.
    Windows uses LOCALAPPDATA (with the conventional profile fallback); other
    platforms use their standard per-user data location so the source tests can
    run portably.
    """
    env = os.environ if environ is None else environ
    user_home = Path.home() if home is None else Path(home)
    os_name = platform_module.system() if system is None else system

    if os_name == "Windows":
        base = env.get("LOCALAPPDATA")
        root = Path(base) if base else user_home / "AppData" / "Local"
    else:
        xdg_data = env.get("XDG_DATA_HOME")
        root = Path(xdg_data) if xdg_data else user_home / ".local" / "share"

    return root / APP_DATA_DIRECTORY / RESULTS_DIRECTORY

