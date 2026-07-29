#!/usr/bin/env python
"""Thin wrapper so the CLI can also be run as `python agent-report.py ...`.

The supported entry point is the installed `agent-report` launcher on PATH (see
scripts\\install-agent-report.ps1). This file exists for the times something
reaches for the source tree instead, and it has to survive being run by an
arbitrary interpreter: agents were hitting

    ModuleNotFoundError: No module named 'agent_report'

because a bare `python agent-report.py` resolves neither the package next to
this file nor its dependencies. So the script puts its own directory on the
path, and re-executes itself in the Agent Deck venv when a dependency is still
missing.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

VENV_PYTHON = HERE.parent / "backend" / ".venv" / "Scripts" / "python.exe"


def _rerun_in_venv() -> int:
    if not VENV_PYTHON.exists():
        raise
    # Guard against looping when the venv itself is the broken interpreter.
    if Path(sys.executable).resolve() == VENV_PYTHON.resolve():
        raise
    return subprocess.call([str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])


if __name__ == "__main__":
    try:
        from agent_report.cli import main
    except ModuleNotFoundError:
        sys.exit(_rerun_in_venv())
    sys.exit(main())
