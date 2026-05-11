RISK_PALETTE = {
    "normal": "#2df59a",
    "suspect": "#ff9f1c",
    "high": "#ff3b4a",
}


def risk_color(level: str) -> str:
    return RISK_PALETTE.get(level, RISK_PALETTE["normal"])


def status_text(level: str) -> str:
    return {
        "normal": "🟢 Normal",
        "suspect": "🟠 Suspect",
        "high": "🔴 Risque élevé",
    }.get(level, "🟢 Normal")


BASE_STYLE = """
QWidget {
    background: #05070d;
    color: #d7f7ff;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background: #05070d;
}

QFrame#Header,
QFrame#Panel,
QFrame#TimelinePanel {
    background: rgba(9, 18, 31, 235);
    border: 1px solid #123d52;
    border-radius: 8px;
}

QFrame#VideoFrame {
    background: #02040a;
    border: 2px solid #2df59a;
    border-radius: 8px;
}

QFrame#MetricCard {
    background: rgba(10, 25, 41, 235);
    border: 1px solid #17475e;
    border-radius: 8px;
}

QLabel#Title {
    color: #e8fbff;
    font-size: 25px;
    font-weight: 700;
}

QLabel#Subtitle {
    color: #79aebd;
    font-size: 12px;
}

QLabel#MetricTitle {
    color: #7eb6c8;
    font-size: 11px;
    font-weight: 600;
}

QLabel#MetricValue {
    color: #eaffff;
    font-size: 23px;
    font-weight: 700;
}

QLabel#SectionTitle {
    color: #aef7ff;
    font-size: 14px;
    font-weight: 700;
}

QLabel#VideoPlaceholder {
    color: #4d7484;
    font-size: 18px;
    font-weight: 600;
}

QPushButton {
    background: #0c2536;
    border: 1px solid #1b5b74;
    border-radius: 6px;
    color: #dffcff;
    font-weight: 600;
    padding: 8px 12px;
}

QPushButton:hover {
    background: #12364c;
    border-color: #2df59a;
}

QPushButton:pressed {
    background: #071923;
}

QPushButton:disabled {
    color: #506b76;
    background: #08131d;
    border-color: #183140;
}

QPushButton#DangerButton {
    border-color: #ff3b4a;
    color: #ffe7e9;
}

QPushButton#DemoButton {
    border-color: #ff9f1c;
    color: #fff0d6;
}

QComboBox,
QLineEdit {
    background: #071622;
    border: 1px solid #1b4d63;
    border-radius: 6px;
    color: #e9fdff;
    padding: 7px 10px;
    min-height: 18px;
}

QComboBox:focus,
QLineEdit:focus {
    border-color: #2df59a;
}

QListWidget {
    background: #050b14;
    border: 1px solid #143f55;
    border-radius: 8px;
    color: #dffcff;
    padding: 6px;
}

QListWidget::item {
    padding: 5px 8px;
    border-bottom: 1px solid #0d2635;
}

QScrollBar:vertical {
    background: #071622;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #1f6079;
    border-radius: 5px;
}
"""
