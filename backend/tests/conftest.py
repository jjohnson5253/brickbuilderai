import sys
from pathlib import Path


# Make the backend package importable consistently regardless of pytest's
# collection order or the directory from which the suite is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
