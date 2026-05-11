from __future__ import annotations

import cv2

from .models import Detection, RiskResult
from .yolo_detector import CONTEXT_OBJECT_LABELS, is_dangerous_label


RISK_COLORS = {
    "normal": (120, 245, 90),
    "suspect": (0, 165, 255),
    "high": (70, 70, 255),
}


def draw_monitor_overlay(frame, detections: list[Detection], result: RiskResult):
    annotated = frame.copy()
    risk_color = RISK_COLORS.get(result.risk_level, RISK_COLORS["normal"])

    for point_a, point_b in result.close_pairs:
        cv2.line(annotated, point_a, point_b, RISK_COLORS["suspect"], 2)

    suspicious_set = set(result.suspicious_objects)
    for detection in detections:
        if detection.label == "person":
            label = "HIGH RISK" if result.risk_level == "high" else "PERSON"
            draw_box(annotated, detection, label, risk_color)
            continue

        if detection in suspicious_set or is_dangerous_label(detection.label):
            color = RISK_COLORS["high"] if result.risk_level == "high" else RISK_COLORS["suspect"]
            label = "WEAPON / THREAT" if is_dangerous_label(detection.label) else "SUSPICIOUS OBJECT"
            draw_box(annotated, detection, label, color)
        elif detection.label in CONTEXT_OBJECT_LABELS and detection in suspicious_set:
            draw_box(annotated, detection, "SUSPICIOUS OBJECT", RISK_COLORS["suspect"])

    draw_risk_banner(annotated, result)
    return annotated


def draw_box(frame, detection: Detection, label: str, color) -> None:
    x1, y1, x2, y2 = detection.box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    caption = f"{label} {detection.confidence:.2f}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.55
    thickness = 1
    text_size, _ = cv2.getTextSize(caption, font, font_scale, thickness)
    text_width, text_height = text_size
    label_y = max(0, y1 - text_height - 10)

    cv2.rectangle(
        frame,
        (x1, label_y),
        (x1 + text_width + 12, label_y + text_height + 10),
        color,
        -1,
    )
    cv2.putText(
        frame,
        caption,
        (x1 + 6, label_y + text_height + 5),
        font,
        font_scale,
        (5, 8, 14),
        thickness,
        cv2.LINE_AA,
    )


def draw_risk_banner(frame, result: RiskResult) -> None:
    color = RISK_COLORS.get(result.risk_level, RISK_COLORS["normal"])
    status_text = {
        "normal": "NORMAL",
        "suspect": "SUSPECT",
        "high": "HIGH RISK",
    }.get(result.risk_level, "NORMAL")

    caption = f"{status_text} | RISK {result.risk_score}%"
    cv2.rectangle(frame, (18, 18), (310, 58), (5, 9, 16), -1)
    cv2.rectangle(frame, (18, 18), (310, 58), color, 2)
    cv2.putText(
        frame,
        caption,
        (32, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        color,
        2,
        cv2.LINE_AA,
    )
