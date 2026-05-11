from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAINING_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = TRAINING_DIR / "dataset"
DEFAULT_CLASSES = TRAINING_DIR / "classes.txt"
DEFAULT_MODEL_OUTPUT = PROJECT_ROOT / "models" / "safecity_weapons.pt"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a custom YOLO model for SafeCity weapon/threat detection."
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Dataset root folder.")
    parser.add_argument("--classes", default=str(DEFAULT_CLASSES), help="Class names file.")
    parser.add_argument("--base-model", default="yolov8s.pt", help="YOLO model to fine-tune.")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", default="8", help="Batch size, or -1 for auto batch.")
    parser.add_argument("--device", default="", help="Example: 0 for GPU, cpu for CPU.")
    parser.add_argument("--name", default="safecity_weapons")
    parser.add_argument("--project", default=str(PROJECT_ROOT / "runs" / "detect"))
    parser.add_argument("--no-install", action="store_true", help="Do not copy best.pt to models/.")
    parser.add_argument("--allow-empty", action="store_true", help="Skip dataset count checks.")
    parser.add_argument("--dry-run", action="store_true", help="Validate config without training.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_root = resolve_path(args.dataset)
    class_names = read_classes(resolve_path(args.classes))

    ensure_dataset_structure(dataset_root)
    if not args.allow_empty:
        validate_dataset(dataset_root)

    data_yaml = write_generated_data_yaml(dataset_root, class_names)
    prepare_ultralytics_config()

    if args.dry_run:
        print(f"Dataset: {dataset_root}")
        print(f"Generated YAML: {data_yaml}")
        print(f"Classes: {len(class_names)}")
        print("Dry run OK. No training started.")
        return 0

    from ultralytics import YOLO

    model = YOLO(args.base_model)
    train_kwargs = {
        "data": str(data_yaml),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": parse_batch(args.batch),
        "name": args.name,
        "project": str(resolve_path(args.project)),
        "exist_ok": True,
    }
    if args.device:
        train_kwargs["device"] = args.device

    results = model.train(**train_kwargs)
    run_dir = Path(getattr(results, "save_dir", resolve_path(args.project) / args.name))
    best_model = run_dir / "weights" / "best.pt"

    if not best_model.exists():
        raise FileNotFoundError(f"Training finished, but best.pt was not found at {best_model}")

    print(f"Best model: {best_model}")

    if not args.no_install:
        DEFAULT_MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best_model, DEFAULT_MODEL_OUTPUT)
        print(f"Installed for SafeCity: {DEFAULT_MODEL_OUTPUT}")
        print("SafeCity will load it automatically at next app start.")

    return 0


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def read_classes(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Class file not found: {path}")

    names = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not names:
        raise ValueError("No class names found.")
    return names


def ensure_dataset_structure(dataset_root: Path) -> None:
    for folder in (
        dataset_root / "images" / "train",
        dataset_root / "images" / "val",
        dataset_root / "labels" / "train",
        dataset_root / "labels" / "val",
    ):
        folder.mkdir(parents=True, exist_ok=True)


def validate_dataset(dataset_root: Path) -> None:
    train_images = list_images(dataset_root / "images" / "train")
    val_images = list_images(dataset_root / "images" / "val")

    if not train_images:
        raise ValueError(
            "No training images found. Add images to training/dataset/images/train "
            "or run with --allow-empty only to test the script."
        )
    if not val_images:
        raise ValueError("No validation images found in training/dataset/images/val.")

    missing_labels = []
    for split, images in (("train", train_images), ("val", val_images)):
        labels_dir = dataset_root / "labels" / split
        for image_path in images:
            if not (labels_dir / f"{image_path.stem}.txt").exists():
                missing_labels.append(str(image_path))

    if missing_labels:
        preview = "\n".join(missing_labels[:10])
        raise ValueError(f"Missing YOLO label files for these images:\n{preview}")


def list_images(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(path for path in folder.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)


def write_generated_data_yaml(dataset_root: Path, class_names: list[str]) -> Path:
    yaml_path = TRAINING_DIR / "data.generated.yaml"
    names_block = "\n".join(f"  {index}: {name}" for index, name in enumerate(class_names))
    yaml_path.write_text(
        f"path: {dataset_root.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        f"{names_block}\n",
        encoding="utf-8",
    )
    return yaml_path


def prepare_ultralytics_config() -> None:
    config_root = PROJECT_ROOT / "logs" / "ultralytics"
    config_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(config_root))


def parse_batch(value: str):
    try:
        return int(value)
    except ValueError:
        return value


if __name__ == "__main__":
    raise SystemExit(main())
