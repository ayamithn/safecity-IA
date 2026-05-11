from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import Detection
from .yolo_detector import (
    WEAPON_OBJECT_LABELS,
    is_dangerous_label,
    normalize_label,
    prepare_ultralytics_config_dir,
    project_root,
)


OPEN_VOCAB_THREAT_CLASSES = [
    "person holding a gun",
    "gun",
    "handgun",
    "pistol",
    "rifle",
    "shotgun",
    "knife",
    "blade",
    "machete",
    "baseball bat",
    "hammer",
    "screwdriver",
    "metal pipe",
    "crowbar",
    "sharp tool",
]


@dataclass
class ThreatDetectorConfig:
    custom_model_path: str = os.getenv("SAFECITY_WEAPON_MODEL", "")
    use_yolo_world: bool = os.getenv("SAFECITY_USE_YOLO_WORLD", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    yolo_world_model: str = os.getenv("SAFECITY_WORLD_MODEL", "yolov8s-worldv2.pt")
    confidence: float = float(os.getenv("SAFECITY_THREAT_CONF", "0.20"))
    image_size: int = int(os.getenv("SAFECITY_THREAT_IMGSZ", "960"))


class ThreatDetector:
    """Optional second detector dedicated to weapons and threatening objects."""

    def __init__(self, config: ThreatDetectorConfig | None = None) -> None:
        self.config = config or ThreatDetectorConfig()
        self._model: Any | None = None
        self._model_kind = ""
        self.error_message = ""
        self.status_message = "Threat detector inactive"

    @property
    def active(self) -> bool:
        return self._model is not None

    def load(self) -> bool:
        if self._model is not None:
            return True

        custom_path = self.config.custom_model_path.strip()
        default_custom_path = project_root() / "models" / "safecity_weapons.pt"
        if not custom_path and default_custom_path.exists():
            custom_path = str(default_custom_path)

        local_world_path = project_root() / self.config.yolo_world_model
        should_use_world = self.config.use_yolo_world or local_world_path.exists()

        if not custom_path and not should_use_world:
            self.status_message = "Threat detector inactive: set SAFECITY_WEAPON_MODEL or SAFECITY_USE_YOLO_WORLD=1"
            return False

        try:
            prepare_ultralytics_config_dir()

            if custom_path:
                from ultralytics import YOLO

                model_path = self._resolve_model_path(custom_path)
                self._model = YOLO(str(model_path))
                self._model_kind = "custom"
                self.status_message = f"Custom: {Path(custom_path).name}"
                self.error_message = ""
                return True

            from ultralytics import YOLOWorld

            model_path = str(local_world_path if local_world_path.exists() else self.config.yolo_world_model)
            self._model = YOLOWorld(model_path)
            self._model.set_classes(OPEN_VOCAB_THREAT_CLASSES)
            self._model_kind = "world"
            self.status_message = f"YOLO-World: {Path(model_path).name}"
            self.error_message = ""
            return True
        except Exception as exc:  # pragma: no cover - depends on model files/runtime.
            self._model = None
            self._model_kind = ""
            self.error_message = f"Threat detector unavailable: {exc}"
            self.status_message = self.error_message
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
            self.error_message = f"Threat inference failed: {exc}"
            self.status_message = self.error_message
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
            label = self._clean_open_vocab_label(str(names.get(class_id, class_id)))

            if not is_dangerous_label(label):
                continue

            x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
            detections.append(
                Detection(
                    label=label,
                    confidence=confidence,
                    box=(x1, y1, x2, y2),
                    source=f"threat-{self._model_kind}",
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
    def _clean_open_vocab_label(label: str) -> str:
        normalized = normalize_label(label)
        if normalized.startswith("person holding a "):
            normalized = normalized.removeprefix("person holding a ")
        if normalized.startswith("person holding "):
            normalized = normalized.removeprefix("person holding ")
        if normalized == "metal pipe":
            return "pipe"
        if normalized == "sharp tool":
            return "sharp object"
        return normalized

    @staticmethod
    def _resolve_model_path(value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = project_root() / path
        return path


def merge_detections(detections: Iterable[Detection]) -> List[Detection]:
    merged: List[Detection] = []

    for detection in detections:
        duplicate_index = _find_duplicate_index(merged, detection)
        if duplicate_index is None:
            merged.append(detection)
            continue

        current = merged[duplicate_index]
        if _detection_priority(detection) > _detection_priority(current):
            merged[duplicate_index] = detection
        elif (
            _detection_priority(detection) == _detection_priority(current)
            and detection.confidence > current.confidence
        ):
            merged[duplicate_index] = detection

    return merged


def _find_duplicate_index(existing: List[Detection], candidate: Detection) -> int | None:
    for index, detection in enumerate(existing):
        if candidate.label == detection.label and _box_iou(candidate.box, detection.box) >= 0.50:
            return index
        if (
            is_dangerous_label(candidate.label)
            and is_dangerous_label(detection.label)
            and _box_iou(candidate.box, detection.box) >= 0.60
        ):
            return index
    return None


def _detection_priority(detection: Detection) -> int:
    if detection.source == "threat-custom":
        return 4
    if detection.source == "threat-world":
        return 3
    if detection.label in WEAPON_OBJECT_LABELS:
        return 2
    return 1


def _box_iou(box_a, box_b) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_width = max(0, inter_x2 - inter_x1)
    inter_height = max(0, inter_y2 - inter_y1)
    intersection = inter_width * inter_height
    if intersection == 0:
        return 0.0

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - intersection
    if union <= 0:
        return 0.0

    return intersection / union
