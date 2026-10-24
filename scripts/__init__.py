"""Build and maintenance scripts: data snapshots, the GPU switch, checks. Run from the repository root, e.g.
`python -m scripts.gpu status`. The app they use lives in src/, so it is put on the import path here."""
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
