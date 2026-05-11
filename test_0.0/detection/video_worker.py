from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, List

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QImage

from .models import Detection, RiskResult
from .risk_analyzer import RiskAnalyzer
from .threat_detector import ThreatDetector, merge_detections
from .visualizer import draw_monitor_overlay
from .yolo_detector import YOLODetector


@dataclass
class SourceConfig:
    kind: str
    value: Any = None
    display_name: str = ""


class VideoWorker(QObject):
    frame_ready = Signal(object)
    telemetry_ready = Signal(dict)
    events_ready = Signal(list)
    finished = Signal()

    def __init__(self, source: SourceConfig) -> None:
        super().__init__()
        self.source = source
        self._running = False
        self._last_event_times: dict[str, float] = {}
        self._detector_error_sent = False
        self._threat_detector_notice_sent = False
        self._frame_index = 0
        self._last_threat_detections: List[Detection] = []
        self.detector = YOLODetector()
        self.threat_detector = ThreatDetector()
        self.analyzer = RiskAnalyzer()

    @Slot()
    def run(self) -> None:
        self._running = True
        try:
            if self.source.kind == "demo":
                self._run_demo()
            else:
                self._run_capture()
        finally:
            self._running = False
            self.finished.emit()

    @Slot()
    def stop(self) -> None:
        self._running = False

    def _run_capture(self) -> None:
        source_value = 0 if self.source.kind == "webcam" else self.source.value
        capture = self._open_capture(source_value)

        if not capture.isOpened():
            self.events_ready.emit([f"Unable to open video source: {self.source.display_name}"])
            self.telemetry_ready.emit(self._empty_telemetry("Source unavailable"))
            return

        model_loaded = self.detector.load()
        if not model_loaded:
            self._emit_detector_warning_once()

        threat_loaded = self.threat_detector.load()
        if threat_loaded:
            self._emit_threat_notice_once(self.threat_detector.status_message)
        elif self.threat_detector.error_message:
            self._emit_threat_notice_once(self.threat_detector.error_message)

        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_delay = 1.0 / fps if fps and fps > 1 else 1.0 / 30.0
        frame_delay = max(0.01, min(frame_delay, 0.08))

        while self._running:
            start_time = time.monotonic()
            ok, frame = capture.read()

            if not ok or frame is None:
                self.events_ready.emit(["Video stream ended"])
                break

            frame = self._resize_frame(frame)
            base_detections = self.detector.detect(frame) if model_loaded else []
            if self.detector.error_message and not self._detector_error_sent:
                self._emit_detector_warning_once()

            threat_detections: List[Detection] = []
            if threat_loaded:
                # Threat scans use a larger image size, so every other frame keeps the UI responsive.
                if self._frame_index % 2 == 0:
                    self._last_threat_detections = self.threat_detector.detect(frame)
                    if self.threat_detector.error_message and not self._threat_detector_notice_sent:
                        self._emit_threat_notice_once(self.threat_detector.error_message)
                threat_detections = self._last_threat_detections

            detections = merge_detections([*base_detections, *threat_detections])
            result = self.analyzer.analyze(detections, frame.shape)
            annotated = draw_monitor_overlay(frame, detections, result)

            self._emit_frame(annotated)
            self._emit_telemetry(result)
            self._emit_throttled_events(result.events)

            self._frame_index += 1
            elapsed = time.monotonic() - start_time
            time.sleep(max(0.001, frame_delay - elapsed))

        capture.release()

    def _run_demo(self) -> None:
        start_time = time.monotonic()
        last_phase_second = 0
        self.analyzer.reset()

        while self._running:
            elapsed = (time.monotonic() - start_time) % 30.0
            phase_second = int(elapsed)
            if phase_second < last_phase_second:
                self.analyzer.reset()
            last_phase_second = phase_second

            frame, detections = self._build_demo_frame(elapsed)
            result = self.analyzer.analyze(detections, frame.shape)
            annotated = draw_monitor_overlay(frame, detections, result)
            self._draw_demo_overlay(annotated, elapsed)

            self._emit_frame(annotated)
            self._emit_telemetry(result)
            self._emit_throttled_events(result.events)
            time.sleep(1.0 / 24.0)

    def _build_demo_frame(self, elapsed: float):
        width, height = 1280, 720
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (8, 12, 22)

        self._draw_demo_grid(frame)

        wave = math.sin(elapsed * 2.2)
        person_a = (330 + int(wave * 8), 225, 455 + int(wave * 8), 620)

        detections: List[Detection] = [
            Detection("person", 0.94, person_a, source="demo"),
        ]

        if elapsed < 10:
            person_b = (860, 220, 985, 620)
        elif elapsed < 20:
            person_b = (505 + int(wave * 28), 225, 630 + int(wave * 28), 620)
            detections.append(Detection("bottle", 0.78, (605, 345, 645, 455), source="demo"))
        else:
            person_b = (492 + int(wave * 18), 225, 617 + int(wave * 18), 620)
            detections.append(Detection("pistol", 0.86, (582, 375, 675, 405), source="demo"))

        detections.append(Detection("person", 0.91, person_b, source="demo"))

        for detection in detections:
            if detection.label == "person":
                self._draw_demo_silhouette(frame, detection)
            else:
                self._draw_demo_object(frame, detection)

        return frame, detections

    @staticmethod
    def _draw_demo_grid(frame) -> None:
        height, width = frame.shape[:2]
        for x in range(0, width, 80):
            cv2.line(frame, (x, 0), (x, height), (18, 42, 52), 1)
        for y in range(0, height, 80):
            cv2.line(frame, (0, y), (width, y), (18, 42, 52), 1)
        cv2.rectangle(frame, (35, 75), (width - 35, height - 35), (30, 80, 92), 1)

    @staticmethod
    def _draw_demo_silhouette(frame, detection: Detection) -> None:
        x1, y1, x2, y2 = detection.box
        center_x = (x1 + x2) // 2
        cv2.circle(frame, (center_x, y1 + 45), 34, (38, 92, 106), -1)
        cv2.rectangle(frame, (x1 + 20, y1 + 90), (x2 - 20, y2), (32, 76, 92), -1)
        cv2.line(frame, (x1 + 15, y1 + 170), (x2 - 15, y1 + 170), (42, 130, 142), 5)

    @staticmethod
    def _draw_demo_object(frame, detection: Detection) -> None:
        color = (0, 122, 255) if detection.label == "bottle" else (55, 55, 255)
        x1, y1, x2, y2 = detection.box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)

    @staticmethod
    def _draw_demo_overlay(frame, elapsed: float) -> None:
        if elapsed < 10:
            phase = "DEMO 0-10s | SECURE AREA"
        elif elapsed < 20:
            phase = "DEMO 10-20s | SUSPICIOUS ACTIVITY"
        else:
            phase = "DEMO 20-30s | ELEVATED RISK"

        cv2.putText(
            frame,
            phase,
            (36, 700),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (140, 245, 220),
            2,
            cv2.LINE_AA,
        )

    def _emit_frame(self, frame) -> None:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_frame.shape
        bytes_per_line = channels * width
        image = QImage(
            rgb_frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        ).copy()
        self.frame_ready.emit(image)

    def _emit_telemetry(self, result: RiskResult) -> None:
        last_event = result.events[-1] if result.events else "No anomaly"
        self.telemetry_ready.emit(
            {
                "people_count": result.people_count,
                "suspicious_count": len(result.suspicious_objects),
                "risk_score": result.risk_score,
                "risk_level": result.risk_level,
                "last_event": last_event,
                "source_name": self.source.display_name,
                "signals": ", ".join(result.signals) if result.signals else "None",
                "threat_detector": self.threat_detector.status_message
                if self.source.kind != "demo"
                else "Demo Scenario",
            }
        )

    def _emit_throttled_events(self, events: list[str]) -> None:
        now = time.monotonic()
        ready_events = []

        for event in events:
            cooldown = 2.5 if event == "Person detected" else 4.0
            previous = self._last_event_times.get(event, 0.0)
            if now - previous >= cooldown:
                ready_events.append(event)
                self._last_event_times[event] = now

        if ready_events:
            self.events_ready.emit(ready_events)

    def _emit_detector_warning_once(self) -> None:
        self._detector_error_sent = True
        message = self.detector.error_message or "YOLO model unavailable."
        self.events_ready.emit([message])

    def _emit_threat_notice_once(self, message: str) -> None:
        self._threat_detector_notice_sent = True
        self.events_ready.emit([message])

    def _empty_telemetry(self, event: str) -> dict:
        return {
            "people_count": 0,
            "suspicious_count": 0,
            "risk_score": 0,
            "risk_level": "normal",
            "last_event": event,
            "source_name": self.source.display_name,
            "signals": "None",
            "threat_detector": self.threat_detector.status_message,
        }

    @staticmethod
    def _resize_frame(frame, max_width: int = 1280):
        height, width = frame.shape[:2]
        if width <= max_width:
            return frame
        ratio = max_width / width
        new_size = (max_width, int(height * ratio))
        return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)

    @staticmethod
    def _open_capture(source_value):
        if source_value != 0:
            return cv2.VideoCapture(source_value)

        for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
            capture = cv2.VideoCapture(0, backend)
            if capture.isOpened():
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                return capture
            capture.release()

        return cv2.VideoCapture(0)
