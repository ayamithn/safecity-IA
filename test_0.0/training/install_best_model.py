from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = PROJECT_ROOT / "runs" / "detect" / "safecity_weapons" / "weights" / "best.pt"
DEFAULT_TARGET = PROJECT_ROOT / "models" / "safecity_weapons.pt"


def main() -> int:
    parser = argparse.ArgumentParser(description="Install a trained SafeCity weapon model.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to best.pt.")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="SafeCity model destination.")
    args = parser.parse_args()

    source = resolve_path(args.source)
    target = resolve_path(args.target)

    if not source.exists():
        raise FileNotFoundError(f"Model not found: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"Installed: {target}")
    print("Restart SafeCity AI Monitor. It will load this model automatically.")
    return 0


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


if __name__ == "__main__":
    raise SystemExit(main())
