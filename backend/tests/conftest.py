import sys
from pathlib import Path

# The backend packages use cross-package relative imports (e.g. agent/loop.py
# does `from ..perception import ...`), which means they are imported as
# `backend.<package>` with the repository root on sys.path — matching how the
# FastAPI app loads them (e.g. `...agent.loop` from api/routers). pytest's
# `pythonpath = ["."]` only puts backend/ on the path, so add the repo root too.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
