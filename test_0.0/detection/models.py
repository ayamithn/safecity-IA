from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


Point = Tuple[int, int]
Box = Tuple[int, int, int, int]


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: Box
    source: str = "model"

    @property
    def x1(self) -> int:
        return self.box[0]

    @property
    def y1(self) -> int:
        return self.box[1]

    @property
    def x2(self) -> int:
        return self.box[2]

    @property
    def y2(self) -> int:
        return self.box[3]

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    @property
    def center(self) -> Point:
        return (self.x1 + self.width // 2, self.y1 + self.height // 2)


@dataclass
class RiskResult:
    risk_score: int
    risk_level: str
    people_count: int
    suspicious_objects: List[Detection] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    events: List[str] = field(default_factory=list)
    close_pairs: List[Tuple[Point, Point]] = field(default_factory=list)
    sudden_motion_count: int = 0
