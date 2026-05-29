import sys
import tomllib
from pathlib import Path

if getattr(sys, "frozen", False):
    _root = Path(getattr(sys, "_MEIPASS"))
else:
    _root = Path(__file__).resolve().parent.parent

with open(_root / "pyproject.toml", "rb") as f:
    __version__ = tomllib.load(f)["project"]["version"]
