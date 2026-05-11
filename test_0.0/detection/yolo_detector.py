from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import Detection


PERSON_LABELS = {"person"}

# Labels commonly returned by custom safety models for weapons/bladed objects.
WEAPON_OBJECT_LABELS = {
    "gun",
    "handgun",
    "pistol",
    "revolver",
    "firearm",
    "rifle",
    "shotgun",
    "assault rifle",
    "weapon",
    "knife",
    "dagger",
    "blade",
    "razor",
    "box cutter",
    "cutter",
    "machete",
    "sword",
    "axe",
}

# COCO-compatible labels plus names often used by custom safety models.
THREAT_OBJECT_LABELS = {
    "knife",
    "scissors",
    "baseball bat",
    "hammer",
    "axe",
    "stick",
    "baton",
    "screwdriver",
    "wrench",
    "crowbar",
    "sharp object",
    "pointed object",
    "metal bar",
    "pipe",
    "weapon",
    "tool",
}

DANGEROUS_OBJECT_LABELS = WEAPON_OBJECT_LABELS | THREAT_OBJECT_LABELS

# These objects are only considered suspicious when the risk analyzer sees
# nearby people and another contextual signal such as close interaction/motion.
CONTEXT_OBJECT_LABELS = {"bottle", "sports ball"}

WEAPON_OBJECT_HINTS = (
    "gun",
    "handgun",
    "pistol",
    "revolver",
    "firearm",
    "rifle",
    "shotgun",
    "weapon",
    "knife",
    "dagger",
    "blade",
    "razor",
    "cutter",
    "machete",
    "sword",
)

THREAT_OBJECT_HINTS = (
    "scissor",
    "bat",
    "hammer",
    "axe",
    "stick",
    "baton",
    "screwdriver",
    "wrench",
    "crowbar",
    "sharp",
    "pointed",
    "metal bar",
    "pipe",
    "tool",
)

CUSTOM_DANGEROUS_HINTS = WEAPON_OBJECT_HINTS + THREAT_OBJECT_HINTS

WATCH_LABELS = PERSON_LABELS | DANGEROUS_OBJECT_LABELS | CONTEXT_OBJECT_LABELS


@dataclass
class DetectorConfig:
    model_path: str = os.getenv("SAFECITY_MODEL", "yolov8n.pt")
    confidence: float = 0.35
    image_size: int = 640
    enabled: bool = True


class YOLODetector:
    """Small wrapper so a custom dangerous-object model can replace YOLO later."""

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()
        self._model: Any | None = None
        self.error_message = ""

    @property
    def available(self) -> bool:
        return self._model is not None

    def load(self) -> bool:
        if not self.config.enabled:
            self.error_message = "YOLO disabled."
            return False

        if self._model is not None:
            return True

        try:
            prepare_ultralytics_config_dir()
            from ultralytics import YOLO

            self._model = YOLO(self.config.model_path)
            self.error_message = ""
            return True
        except Exception as exc:  # pragma: no cover - depends on local install/model.
            self._model = None
            self.error_message = f"YOLO unavailable: {exc}"
            return False

    def detect(self, frame) -> List[Detection]:
        if self._model is None and not self.load():
            return []

        try:
            results = self._model.predict(
                frame,
                conf=self.config.confidence,
                imgsz=self.config.image_size,
                verbose=False,
            )
        except Exception as exc:  # pragma: no cover - runtime/model specific.
            self.error_message = f"YOLO inference failed: {exc}"
            return []

        if not results:
            return []

        result = results[0]
        names = self._names_to_dict(getattr(result, "names", {}))
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        detections: List[Detection] = []
        for box in boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            label = normalize_label(str(names.get(class_id, class_id)))

            if not self._is_watched_label(label):
                continue

            x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
            detections.append(
                Detection(
                    label=label,
                    confidence=confidence,
                    box=(x1, y1, x2, y2),
                    source="yolo",
                )
            )

        return detections

    @staticmethod
    def _names_to_dict(names: Any) -> Dict[int, str]:
        if isinstance(names, dict):
            return {int(key): str(value) for key, value in names.items()}
        if isinstance(names, Iterable):
            return {index: str(value) for index, value in enumerate(names)}
        return {}

    @staticmethod
    def _is_watched_label(label: str) -> bool:
        if label in WATCH_LABELS:
            return True
        return any(hint in label for hint in CUSTOM_DANGEROUS_HINTS)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def prepare_ultralytics_config_dir() -> None:
    config_root = project_root() / "logs" / "ultralytics"
    config_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(config_root))


def normalize_label(label: str) -> str:
    return " ".join(label.lower().replace("_", " ").replace("-", " ").split())


def is_weapon_label(label: str) -> bool:
    normalized = normalize_label(label)
    if normalized in WEAPON_OBJECT_LABELS:
        return True
    return any(hint in normalized for hint in WEAPON_OBJECT_HINTS)


def is_dangerous_label(label: str) -> bool:
    normalized = normalize_label(label)
    if normalized in DANGEROUS_OBJECT_LABELS:
        return True
    return any(hint in normalized for hint in CUSTOM_DANGEROUS_HINTS)
