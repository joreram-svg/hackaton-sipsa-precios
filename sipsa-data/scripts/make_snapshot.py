import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sipsa.snapshot import make_snapshot


if __name__ == "__main__":
    for filename in make_snapshot():
        print(filename)
