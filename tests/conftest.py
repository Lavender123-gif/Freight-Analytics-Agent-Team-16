import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# A fresh clone has no data/ folder (it is git-ignored). pytest creates --basetemp itself but not its
# parent folders, so create them here; otherwise every test that uses tmp_path errors on a new machine.
(Path(__file__).parents[1] / "data" / "interim").mkdir(parents=True, exist_ok=True)
