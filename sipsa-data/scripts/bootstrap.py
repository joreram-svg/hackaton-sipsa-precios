import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sipsa.ingest.pipeline import run_ingest


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicializa SIPSA Data e ingesta su histórico")
    parser.add_argument("--source", choices=["seed", "auto"], default="auto")
    args = parser.parse_args()
    result = run_ingest(args.source)
    print(result)


if __name__ == "__main__":
    main()
