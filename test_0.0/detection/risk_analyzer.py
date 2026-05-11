from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List

from .models import Detection, Point, RiskResult
from .yolo_detector import CONTEXT_OBJECT_LABELS, is_dangerous_label, is_weapon_label


@dataclass
class RiskConfig:
    close_distance_ratio: float = 0.18
    sudden_motion_ratio: float = 0.10
    object_person_ratio: float = 0.16
    horizontal_person_ratio: float = 1.35


class RiskAnalyzer:
    """Approximate anomaly scoring without identity, face recognition or claims of certainty."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.previous_person_centers: List[Point] = []

    def reset(self) -> None:
        self.previous_person_centers.clear()

    def analyze(self, detections: Iterable[Detection], frame_shape) -> RiskResult:
        detections = list(detections)
        frame_height, frame_width = frame_shape[:2]
        diagonal = max(1.0, math.hypot(frame_width, frame_height))

        close_threshold = diagonal * self.config.close_distance_ratio
        motion_threshold = diagonal * self.config.sudden_motion_ratio
        object_threshold = diagonal * self.config.object_person_ratio

        people = [item for item in detections if item.label == "person"]
        objects = [item for item in detections if item.label != "person"]

        score = 0
        signals: List[str] = []
        events: List[str] = []
        suspicious_objects: List[Detection] = []
        close_pairs: List[tuple[Point, Point]] = []

        if people:
            events.append("Person detected")

        for index, person_a in enumerate(people):
            for person_b in people[index + 1 :]:
                distance = self._distance(person_a.center, person_b.center)
                if distance <= close_threshold:
                    close_pairs.append((person_a.center, person_b.center))

        if close_pairs:
            score += 25
            signals.append("close_interaction")
            events.append("Close interaction detected")

        sudden_motion_count = self._count_sudden_motion(people, motion_threshold)
        if sudden_motion_count:
            score += min(30, 15 + sudden_motion_count * 8)
            signals.append("sudden_motion")
            events.append("Sudden movement detected")

        horizontal_people = [
            person
            for person in people
            if person.height > 0
            and person.width / person.height >= self.config.horizontal_person_ratio
        ]
        if horizontal_people:
            score += 25
            signals.append("abnormal_posture")
            events.append("Abnormal posture detected")

        visible_weapons = [item for item in objects if is_weapon_label(item.label)]
        visible_dangerous = [item for item in objects if is_dangerous_label(item.label)]
        nearby_dangerous = [
            item
            for item in visible_dangerous
            if self._nearest_person_distance(item, people) <= object_threshold
        ]
        nearby_weapons = [
            item
            for item in visible_weapons
            if self._nearest_person_distance(item, people) <= object_threshold
        ]

        if visible_weapons:
            score += 45
            signals.append("weapon_or_threat_visible")
            events.append("Weapon or threatening object detected")
            suspicious_objects.extend(visible_weapons)
        elif visible_dangerous:
            score += 35
            signals.append("dangerous_object_visible")
            events.append("Threatening object detected")
            suspicious_objects.extend(visible_dangerous)

        if nearby_weapons:
            score += 45
            signals.append("weapon_or_threat_near_person")
            events.append("Weapon or threat near person detected")
        elif nearby_dangerous:
            score += 35
            signals.append("dangerous_object_near_person")
            events.append("Threatening object near person detected")

        contextual_objects = [
            item
            for item in objects
            if item.label in CONTEXT_OBJECT_LABELS
            and self._nearest_person_distance(item, people) <= object_threshold
        ]
        if contextual_objects and (close_pairs or sudden_motion_count):
            score += 20
            signals.append("context_object_near_person")
            events.append("Suspicious object detected")
            suspicious_objects.extend(contextual_objects)

        if len(set(signals)) >= 2:
            score += 15
            events.append("Multiple anomaly signals detected")

        score = max(0, min(100, score))
        if nearby_weapons or nearby_dangerous or score >= 70:
            risk_level = "high"
            events.append("High risk situation detected")
        elif score >= 35:
            risk_level = "suspect"
        else:
            risk_level = "normal"

        self.previous_person_centers = [person.center for person in people]

        return RiskResult(
            risk_score=score,
            risk_level=risk_level,
            people_count=len(people),
            suspicious_objects=self._unique_detections(suspicious_objects),
            signals=self._unique_strings(signals),
            events=self._unique_strings(events),
            close_pairs=close_pairs,
            sudden_motion_count=sudden_motion_count,
        )

    def _count_sudden_motion(
        self, people: List[Detection], motion_threshold: float
    ) -> int:
        if not self.previous_person_centers:
            return 0

        count = 0
        unused_previous = self.previous_person_centers.copy()

        for person in people:
            if not unused_previous:
                break
            nearest = min(unused_previous, key=lambda point: self._distance(person.center, point))
            distance = self._distance(person.center, nearest)
            unused_previous.remove(nearest)
            if distance >= motion_threshold:
                count += 1

        return count

    @staticmethod
    def _nearest_person_distance(item: Detection, people: List[Detection]) -> float:
        if not people:
            return float("inf")
        return min(RiskAnalyzer._distance(item.center, person.center) for person in people)

    @staticmethod
    def _distance(point_a: Point, point_b: Point) -> float:
        return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])

    @staticmethod
    def _unique_strings(values: Iterable[str]) -> List[str]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _unique_detections(values: Iterable[Detection]) -> List[Detection]:
        return list(dict.fromkeys(values))
