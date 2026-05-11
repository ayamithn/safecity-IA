from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QThread,
)
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from detection.video_worker import SourceConfig, VideoWorker
from ui.styles import BASE_STYLE, risk_color, status_text


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "--") -> None:
        super().__init__()
        self.setObjectName("MetricCard")
        self.setMinimumHeight(82)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_accent(self, color: str) -> None:
        self.value_label.setStyleSheet(f"color: {color};")
        self.setStyleSheet(
            "QFrame#MetricCard {"
            "background: rgba(10, 25, 41, 235);"
            f"border: 1px solid {color};"
            "border-radius: 8px;"
            "}"
        )


class SafeCityMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SafeCity AI Monitor")
        self.resize(1380, 860)
        self.setMinimumSize(QSize(1120, 720))
        self.setStyleSheet(BASE_STYLE)

        self.worker: VideoWorker | None = None
        self.thread: QThread | None = None
        self.current_image = None
        self.video_path = ""
        self.alert_count = 0
        self.current_level = "normal"
        self.log_path = Path(__file__).resolve().parent.parent / "logs" / "events.log"

        self._build_ui()
        self._configure_glow()
        self._source_changed()
        self._apply_risk_state("normal")

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)
        self.setCentralWidget(root)

        root_layout.addWidget(self._build_header())

        body_layout = QHBoxLayout()
        body_layout.setSpacing(12)
        body_layout.addWidget(self._build_video_panel(), stretch=1)
        body_layout.addWidget(self._build_dashboard())
        root_layout.addLayout(body_layout, stretch=1)

        root_layout.addWidget(self._build_timeline(), stretch=0)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        title_group = QVBoxLayout()
        title_group.setSpacing(2)
        title = QLabel("SafeCity AI Monitor")
        title.setObjectName("Title")
        subtitle = QLabel("Prototype de détection d'anomalies vidéo sans reconnaissance faciale")
        subtitle.setObjectName("Subtitle")
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        layout.addLayout(title_group, stretch=1)

        self.status_badge = QLabel(status_text("normal"))
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setMinimumWidth(150)
        layout.addWidget(self.status_badge)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Webcam PC", "Caméra téléphone IP", "Vidéo locale"])
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        layout.addWidget(self.source_combo)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://192.168.1.100:8080/video")
        self.url_input.setMinimumWidth(250)
        layout.addWidget(self.url_input)

        self.browse_button = QPushButton("Choisir vidéo")
        self.browse_button.clicked.connect(self._browse_video)
        layout.addWidget(self.browse_button)

        self.start_button = QPushButton("Démarrer")
        self.start_button.clicked.connect(self._start_current_source)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Arrêter")
        self.stop_button.setObjectName("DangerButton")
        self.stop_button.clicked.connect(self._stop_worker)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.demo_button = QPushButton("Demo Scenario")
        self.demo_button.setObjectName("DemoButton")
        self.demo_button.clicked.connect(self._start_demo)
        layout.addWidget(self.demo_button)

        return header

    def _build_video_panel(self) -> QFrame:
        self.video_frame = QFrame()
        self.video_frame.setObjectName("VideoFrame")
        layout = QVBoxLayout(self.video_frame)
        layout.setContentsMargins(10, 10, 10, 10)

        self.video_label = QLabel("SafeCity AI Monitor\nAucune source active")
        self.video_label.setObjectName("VideoPlaceholder")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(740, 420)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self.video_label)

        return self.video_frame

    def _build_dashboard(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setFixedWidth(330)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        section_title = QLabel("Dashboard")
        section_title.setObjectName("SectionTitle")
        layout.addWidget(section_title)

        self.people_card = MetricCard("PERSONNES DÉTECTÉES", "0")
        self.objects_card = MetricCard("MENACES / OBJETS", "0")
        self.risk_card = MetricCard("SCORE DE RISQUE", "0%")
        self.source_card = MetricCard("SOURCE VIDÉO", "Aucune")
        self.threat_model_card = MetricCard("DÉTECTEUR MENACES", "Standard")
        self.threat_model_card.value_label.setStyleSheet("font-size: 15px;")
        self.alert_card = MetricCard("COMPTEUR D'ALERTES", "0")

        layout.addWidget(self.people_card)
        layout.addWidget(self.objects_card)
        layout.addWidget(self.risk_card)
        layout.addWidget(self.source_card)
        layout.addWidget(self.threat_model_card)
        layout.addWidget(self.alert_card)

        last_event_title = QLabel("DERNIER ÉVÉNEMENT")
        last_event_title.setObjectName("MetricTitle")
        self.last_event_label = QLabel("No anomaly")
        self.last_event_label.setWordWrap(True)
        self.last_event_label.setMinimumHeight(56)

        signals_title = QLabel("SIGNAUX ACTIFS")
        signals_title.setObjectName("MetricTitle")
        self.signals_label = QLabel("None")
        self.signals_label.setWordWrap(True)

        layout.addWidget(last_event_title)
        layout.addWidget(self.last_event_label)
        layout.addWidget(signals_title)
        layout.addWidget(self.signals_label)
        layout.addStretch(1)

        return panel

    def _build_timeline(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("TimelinePanel")
        panel.setMinimumHeight(170)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("Timeline des alertes")
        title.setObjectName("SectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)

        clear_button = QPushButton("Effacer")
        clear_button.clicked.connect(self.timeline_list_clear)
        title_row.addWidget(clear_button)

        layout.addLayout(title_row)

        self.timeline_list = QListWidget()
        layout.addWidget(self.timeline_list)
        return panel

    def _configure_glow(self) -> None:
        self.glow_effect = QGraphicsDropShadowEffect(self.video_frame)
        self.glow_effect.setOffset(0, 0)
        self.glow_effect.setBlurRadius(22)
        self.video_frame.setGraphicsEffect(self.glow_effect)

        self.pulse_animation = QPropertyAnimation(self.glow_effect, b"blurRadius", self)
        self.pulse_animation.setStartValue(18)
        self.pulse_animation.setEndValue(42)
        self.pulse_animation.setDuration(850)
        self.pulse_animation.setLoopCount(-1)
        self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutSine)

    def _source_changed(self) -> None:
        selected = self.source_combo.currentText()
        is_ip = selected == "Caméra téléphone IP"
        is_file = selected == "Vidéo locale"
        self.url_input.setEnabled(is_ip)
        self.url_input.setVisible(is_ip)
        self.browse_button.setEnabled(is_file)
        self.browse_button.setVisible(is_file)

    def _browse_video(self) -> bool:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une vidéo",
            "",
            "Videos (*.mp4 *.avi *.mov *.mkv *.webm);;Tous les fichiers (*.*)",
        )
        if not path:
            return False
        self.video_path = path
        self.source_card.set_value(Path(path).name)
        return True

    def _start_current_source(self) -> None:
        selected = self.source_combo.currentText()

        if selected == "Webcam PC":
            config = SourceConfig("webcam", 0, "Webcam PC")
        elif selected == "Caméra téléphone IP":
            url = self.url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "URL requise", "Ajoutez l'URL de la caméra IP.")
                return
            config = SourceConfig("url", url, "Caméra téléphone IP")
        else:
            if not self.video_path and not self._browse_video():
                return
            config = SourceConfig("file", self.video_path, Path(self.video_path).name)

        self._start_worker(config)

    def _start_demo(self) -> None:
        self._start_worker(SourceConfig("demo", None, "Demo Scenario"))

    def _start_worker(self, config: SourceConfig) -> None:
        if self.thread is not None:
            return

        self.alert_count = 0
        self.alert_card.set_value("0")
        self.timeline_list.clear()
        self.source_card.set_value(config.display_name)
        self.last_event_label.setText("Starting source...")

        self.thread = QThread(self)
        self.worker = VideoWorker(config)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.frame_ready.connect(self._update_frame)
        self.worker.telemetry_ready.connect(self._update_telemetry)
        self.worker.events_ready.connect(self._append_events)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_finished)
        self.thread.finished.connect(self.thread.deleteLater)

        self.start_button.setEnabled(False)
        self.demo_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.thread.start()

    def _stop_worker(self) -> None:
        if self.worker is not None:
            self.worker.stop()
        self.stop_button.setEnabled(False)
        self.last_event_label.setText("Stopping source...")

    def _thread_finished(self) -> None:
        self.worker = None
        self.thread = None
        self.start_button.setEnabled(True)
        self.demo_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _update_frame(self, image) -> None:
        self.current_image = image
        self._render_current_frame()

    def _render_current_frame(self) -> None:
        if self.current_image is None:
            return
        pixmap = QPixmap.fromImage(self.current_image)
        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)

    def _update_telemetry(self, telemetry: dict) -> None:
        level = telemetry.get("risk_level", "normal")
        self.people_card.set_value(str(telemetry.get("people_count", 0)))
        self.objects_card.set_value(str(telemetry.get("suspicious_count", 0)))
        self.risk_card.set_value(f"{telemetry.get('risk_score', 0)}%")
        self.source_card.set_value(str(telemetry.get("source_name", "Aucune")))
        self.threat_model_card.set_value(str(telemetry.get("threat_detector", "Standard")))
        self.last_event_label.setText(str(telemetry.get("last_event", "No anomaly")))
        self.signals_label.setText(str(telemetry.get("signals", "None")))
        self._apply_risk_state(level)

    def _append_events(self, events: list[str]) -> None:
        for event in events:
            timestamp = datetime.now().strftime("%H:%M:%S")
            item = QListWidgetItem(f"[{timestamp}] {event}")
            item.setForeground(QColor(self._event_color(event)))
            self.timeline_list.addItem(item)
            self._write_event_log(timestamp, event)

            if self._is_alert_event(event):
                self.alert_count += 1

        self.alert_card.set_value(str(self.alert_count))
        self.timeline_list.scrollToBottom()

    def timeline_list_clear(self) -> None:
        self.timeline_list.clear()
        self.alert_count = 0
        self.alert_card.set_value("0")

    def _apply_risk_state(self, level: str) -> None:
        color = risk_color(level)
        self.current_level = level
        self.status_badge.setText(status_text(level))
        self.status_badge.setStyleSheet(
            "QLabel {"
            f"border: 1px solid {color};"
            f"color: {color};"
            "background: rgba(5, 12, 20, 235);"
            "border-radius: 8px;"
            "font-weight: 700;"
            "padding: 8px 12px;"
            "}"
        )
        self.video_frame.setStyleSheet(
            "QFrame#VideoFrame {"
            "background: #02040a;"
            f"border: 2px solid {color};"
            "border-radius: 8px;"
            "}"
        )
        self.risk_card.set_accent(color)
        self.glow_effect.setColor(QColor(color))

        if level == "normal":
            self.pulse_animation.stop()
            self.glow_effect.setBlurRadius(18)
        elif self.pulse_animation.state() != QAbstractAnimation.State.Running:
            self.pulse_animation.start()

    @staticmethod
    def _event_color(event: str) -> str:
        if "High risk" in event:
            return risk_color("high")
        if any(
            keyword in event
            for keyword in (
                "Suspicious",
                "Threat",
                "Weapon",
                "Close",
                "Sudden",
                "Multiple",
                "Abnormal",
            )
        ):
            return risk_color("suspect")
        return risk_color("normal")

    @staticmethod
    def _is_alert_event(event: str) -> bool:
        ignored = (
            "Person detected",
            "Video stream ended",
            "YOLO-World",
            "Custom threat model",
            "Custom:",
            "Threat detector",
        )
        return not event.startswith(ignored) and not event.startswith("YOLO")

    def _write_event_log(self, timestamp: str, event: str) -> None:
        self.log_path.parent.mkdir(exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{datetime.now().date()} {timestamp} - {event}\n")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_current_frame()

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            self.worker.stop()
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait(1500)
        event.accept()
