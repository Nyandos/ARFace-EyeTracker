import sys
import os
import socket
from typing import Optional, List, Tuple, Dict
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QSlider, QComboBox, QFrame, QTabWidget
)
from core.receiver import UDPReceiver
from core.calibrator import Calibrator
from core.geometry import GeometryEstimator
from .hud_overlay import HUDOverlay
from .calib_window import CalibrationWindow

# -------------------------------------------------------------------------
# Hallmark "Tally" Preset Design Tokens (Modern-Minimal / High-Utility Dark)
# -------------------------------------------------------------------------
TALLY_STYLE = """
/* Base Canvas */
QMainWindow {
    background-color: #0b0f17;
}
QWidget {
    color: #f3f4f6;
    font-family: 'Segoe UI', -apple-system, 'Inter', sans-serif;
    font-size: 12px;
}

/* Surface Cards */
QFrame.tally-card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 14px;
}
QFrame.tally-card-elevated {
    background-color: #161f30;
    border: 1px solid #2d3748;
    border-radius: 8px;
    padding: 12px;
}

/* Typography Hierarchy */
QLabel.tally-section-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #9ca3af;
    margin-bottom: 4px;
}
QLabel.tally-value-mono {
    font-family: 'Consolas', 'Cascadia Code', 'Menlo', monospace;
    font-size: 12px;
    color: #e5e7eb;
}
QLabel.tally-metric-large {
    font-family: 'Consolas', 'Cascadia Code', 'Menlo', monospace;
    font-size: 20px;
    font-weight: 700;
    color: #f9fafb;
}

/* Buttons: 8-State Compliant */
QPushButton {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
    font-size: 12px;
    color: #f3f4f6;
}
QPushButton:hover {
    background-color: #283548;
    border-color: #4b5563;
    color: #ffffff;
}
QPushButton:focus {
    border-color: #38bdf8;
    outline: none;
}
QPushButton:pressed {
    background-color: #111827;
    border-color: #1f2937;
}
QPushButton:disabled {
    background-color: #111827;
    border-color: #1f2937;
    color: #4b5563;
}

/* Primary Action Button */
QPushButton.tally-primary-btn {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
    color: #ffffff;
}
QPushButton.tally-primary-btn:hover {
    background-color: #0369a1;
    border-color: #7dd3fc;
}
QPushButton.tally-primary-btn:pressed {
    background-color: #0c4a6e;
}

/* Accent Action (Calibration) */
QPushButton.tally-accent-btn {
    background-color: #059669;
    border: 1px solid #34d399;
    color: #ffffff;
}
QPushButton.tally-accent-btn:hover {
    background-color: #047857;
    border-color: #6ee7b7;
}
QPushButton.tally-accent-btn:pressed {
    background-color: #064e3b;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 4px;
    background: #1f2937;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #0284c7;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #f9fafb;
    border: 2px solid #0284c7;
    width: 14px;
    height: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #ffffff;
    border-color: #38bdf8;
}

/* Combobox */
QComboBox {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 5px 10px;
    color: #f3f4f6;
    font-weight: 500;
}
QComboBox:hover {
    border-color: #4b5563;
}
QComboBox:focus {
    border-color: #38bdf8;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #111827;
    border: 1px solid #374151;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
    color: #f3f4f6;
    padding: 4px;
}
"""

COLOR_THEMES = {
    "Cyan (0, 240, 255)": QColor(0, 240, 255, 220),
    "Emerald (52, 211, 153)": QColor(52, 211, 153, 220),
    "Crimson (244, 63, 94)": QColor(244, 63, 94, 220),
    "Amber (251, 191, 36)": QColor(251, 191, 36, 220),
    "Purple (192, 132, 252)": QColor(192, 132, 252, 220),
    "Mono White (255, 255, 255)": QColor(255, 255, 255, 230),
}

FILTER_PRESETS = {
    "⚡ Ultra-Smooth (Butter Glide / Recommended)": (0.4, 0.008),
    "⚖️ Responsive (Balanced Tracking)": (0.8, 0.02),
    "🛡️ Maximum Damping (Zero-Jitter Lock)": (0.25, 0.004),
}

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class LiveIndicator(QWidget):
    """
    Minimalist LED Pulse Indicator (Tally Style)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self.is_active = False

    def set_active(self, active: bool):
        if self.is_active != active:
            self.is_active = active
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        color = QColor(16, 185, 129) if self.is_active else QColor(239, 68, 68)
        # Core dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(1, 1, 8, 8)


class ControlPanel(QMainWindow):
    """
    Hallmark 'Tally' Redesigned Control Panel.
    High-density, structured, honest-copy utility GUI for ARFace-Eyetracker.
    """
    def __init__(self, receiver: UDPReceiver, calibrator: Calibrator, hud: HUDOverlay, calib_win: CalibrationWindow, geometry: Optional[GeometryEstimator] = None):
        super().__init__()
        self.receiver = receiver
        self.calibrator = calibrator
        self.hud = hud
        self.calib_win = calib_win
        self.geometry = geometry or calibrator.geometry

        self.setWindowTitle("ARFace-Eyetracker — Control Center")
        self.setFixedSize(580, 690)
        self.setStyleSheet(TALLY_STYLE)

        self._init_ui()

        # Signals
        self.calib_win.calibration_finished.connect(self._on_calibration_finished)

        # 10Hz Status Polling
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_telemetry)
        self.status_timer.start(100)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 18, 20, 20)
        main_layout.setSpacing(14)

        # ---------------------------------------------------------
        # Top Header Bar: Title + Connection Badge + Quick Actions
        # ---------------------------------------------------------
        header_bar = QHBoxLayout()
        
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("ARFACE // EYETRACKER")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; letter-spacing: 1.2px; color: #f9fafb;")
        sub_lbl = QLabel("TrueDepth 3D Gaze Engine (60Hz–240Hz+)")
        sub_lbl.setStyleSheet("font-size: 11px; color: #6b7280; font-weight: 500;")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        header_bar.addLayout(title_col)

        header_bar.addStretch()

        # Status Tag Badge
        self.badge_frame = QFrame()
        self.badge_frame.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 16px;
                padding: 4px 10px;
            }
        """)
        badge_layout = QHBoxLayout(self.badge_frame)
        badge_layout.setContentsMargins(6, 3, 8, 3)
        badge_layout.setSpacing(6)
        
        self.live_indicator = LiveIndicator()
        self.badge_text = QLabel("STANDBY")
        self.badge_text.setStyleSheet("font-size: 11px; font-weight: 700; color: #9ca3af; letter-spacing: 0.5px;")
        badge_layout.addWidget(self.live_indicator)
        badge_layout.addWidget(self.badge_text)
        header_bar.addWidget(self.badge_frame)

        main_layout.addLayout(header_bar)

        # ---------------------------------------------------------
        # Section 1: Telemetry & Network Feed (High-Density Grid)
        # ---------------------------------------------------------
        feed_card = QFrame()
        feed_card.setProperty("class", "tally-card")
        feed_layout = QVBoxLayout(feed_card)
        feed_layout.setSpacing(10)

        # Header of Feed
        feed_head = QHBoxLayout()
        feed_title = QLabel("TELEMETRY & INGEST")
        feed_title.setProperty("class", "tally-section-title")
        local_ip = get_local_ip()
        self.ip_display = QLabel(f"UDP Target: {local_ip}:{self.receiver.port}")
        self.ip_display.setStyleSheet("font-family: monospace; font-size: 11px; color: #38bdf8;")
        feed_head.addWidget(feed_title)
        feed_head.addStretch()
        feed_head.addWidget(self.ip_display)
        feed_layout.addLayout(feed_head)

        # Port Selector row (Standard 5005 vs iFacialMocap 49983)
        port_row = QHBoxLayout()
        port_lbl = QLabel("Ingest Port:")
        port_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        
        self.btn_port_5005 = QPushButton("5005 (Standard)")
        self.btn_port_5005.setProperty("class", "tally-primary-btn" if self.receiver.port == 5005 else "")
        self.btn_port_5005.clicked.connect(lambda: self._switch_port(5005))

        self.btn_port_ifacial = QPushButton("49983 (iFacialMocap)")
        self.btn_port_ifacial.setProperty("class", "tally-primary-btn" if self.receiver.port == 49983 else "")
        self.btn_port_ifacial.clicked.connect(lambda: self._switch_port(49983))

        port_row.addWidget(port_lbl)
        port_row.addWidget(self.btn_port_5005)
        port_row.addWidget(self.btn_port_ifacial)
        port_row.addStretch()
        feed_layout.addLayout(port_row)

        # Metric Columns (Rate, Packets, Head Pose, Gaze Ray)
        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(14)
        metrics_grid.setVerticalSpacing(8)

        # Box 1: FPS Rate
        b1 = QFrame()
        b1.setProperty("class", "tally-card-elevated")
        b1_l = QVBoxLayout(b1)
        b1_l.setContentsMargins(10, 8, 10, 8)
        b1_lbl = QLabel("STREAM RATE")
        b1_lbl.setStyleSheet("font-size: 10px; font-weight: 600; color: #9ca3af;")
        self.fps_val = QLabel("0.0 FPS")
        self.fps_val.setProperty("class", "tally-metric-large")
        b1_l.addWidget(b1_lbl)
        b1_l.addWidget(self.fps_val)
        metrics_grid.addWidget(b1, 0, 0)

        # Box 2: Total Packets
        b2 = QFrame()
        b2.setProperty("class", "tally-card-elevated")
        b2_l = QVBoxLayout(b2)
        b2_l.setContentsMargins(10, 8, 10, 8)
        b2_lbl = QLabel("PACKETS RECEIVED")
        b2_lbl.setStyleSheet("font-size: 10px; font-weight: 600; color: #9ca3af;")
        self.packets_val = QLabel("0")
        self.packets_val.setProperty("class", "tally-metric-large")
        b2_l.addWidget(b2_lbl)
        b2_l.addWidget(self.packets_val)
        metrics_grid.addWidget(b2, 0, 1)

        feed_layout.addLayout(metrics_grid)

        # 3D Vector Readout Row
        vec_row = QHBoxLayout()
        self.head_vec_lbl = QLabel("Head Pose: X:+0.00 Y:+0.00 Z:+0.00m")
        self.head_vec_lbl.setProperty("class", "tally-value-mono")
        self.head_vec_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        
        self.gaze_signal_lbl = QLabel("Eye Signal: WAITING...")
        self.gaze_signal_lbl.setProperty("class", "tally-value-mono")
        self.gaze_signal_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")

        vec_row.addWidget(self.head_vec_lbl)
        vec_row.addStretch()
        vec_row.addWidget(self.gaze_signal_lbl)
        feed_layout.addLayout(vec_row)

        # Raw Packet Stream Inspector (for troubleshooting)
        self.raw_packet_lbl = QLabel("Raw Feed: [ Waiting for UDP stream... ]")
        self.raw_packet_lbl.setProperty("class", "tally-value-mono")
        self.raw_packet_lbl.setStyleSheet("color: #6b7280; font-size: 10px; background-color: #0b0f17; padding: 4px 8px; border-radius: 4px;")
        feed_layout.addWidget(self.raw_packet_lbl)

        main_layout.addWidget(feed_card)

        # ---------------------------------------------------------
        # Section 2: Spatial Calibration (9-Point Solver)
        # ---------------------------------------------------------
        calib_card = QFrame()
        calib_card.setProperty("class", "tally-card")
        calib_layout = QVBoxLayout(calib_card)
        calib_layout.setSpacing(10)

        calib_head = QHBoxLayout()
        calib_title = QLabel("GEOMETRIC CALIBRATION")
        calib_title.setProperty("class", "tally-section-title")
        self.calib_status_badge = QLabel(
            "[ ACTIVE MATRIX ]" if self.calibrator.is_calibrated else "[ DEFAULT PROJECTION ]"
        )
        self.calib_status_badge.setStyleSheet(
            "font-family: monospace; font-size: 11px; font-weight: 700; color: #10b981;" if self.calibrator.is_calibrated
            else "font-family: monospace; font-size: 11px; font-weight: 700; color: #f59e0b;"
        )
        calib_head.addWidget(calib_title)
        calib_head.addStretch()
        calib_head.addWidget(self.calib_status_badge)
        calib_layout.addLayout(calib_head)

        calib_actions = QHBoxLayout()
        self.calib_start_btn = QPushButton("Execute 3D Multi-Pose Calibration (Grid + Head-Tilt)")
        self.calib_start_btn.setProperty("class", "tally-accent-btn")
        self.calib_start_btn.clicked.connect(self._start_calibration)
        calib_actions.addWidget(self.calib_start_btn, 3)

        self.calib_reset_btn = QPushButton("Reset Matrix")
        self.calib_reset_btn.clicked.connect(self._reset_calibration)
        calib_actions.addWidget(self.calib_reset_btn, 1)
        calib_layout.addLayout(calib_actions)

        self.calib_notice_lbl = QLabel("")
        self.calib_notice_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        calib_layout.addWidget(self.calib_notice_lbl)

        main_layout.addWidget(calib_card)

        # ---------------------------------------------------------
        # Section 3: Overlay Appearance & Dynamic Filtering
        # ---------------------------------------------------------
        opt_card = QFrame()
        opt_card.setProperty("class", "tally-card")
        opt_layout = QVBoxLayout(opt_card)
        opt_layout.setSpacing(12)

        opt_title = QLabel("RENDERER & 1€ FILTER DYNAMICS")
        opt_title.setProperty("class", "tally-section-title")
        opt_layout.addWidget(opt_title)

        # Palette & Filter Selectors Row
        selectors_grid = QGridLayout()
        selectors_grid.setHorizontalSpacing(14)
        selectors_grid.setVerticalSpacing(8)

        # Theme Selector
        selectors_grid.addWidget(QLabel("Reticle Palette:"), 0, 0)
        self.color_combo = QComboBox()
        for name in COLOR_THEMES.keys():
            self.color_combo.addItem(name)
        self.color_combo.currentIndexChanged.connect(self._on_style_changed)
        selectors_grid.addWidget(self.color_combo, 0, 1)

        # Filter Dynamics Selector
        selectors_grid.addWidget(QLabel("Tracking Profile:"), 1, 0)
        self.smooth_combo = QComboBox()
        for name in FILTER_PRESETS.keys():
            self.smooth_combo.addItem(name)
        self.smooth_combo.currentIndexChanged.connect(self._on_smoothing_changed)
        selectors_grid.addWidget(self.smooth_combo, 1, 1)

        opt_layout.addLayout(selectors_grid)

        # Sliders Row (Gaze Sensitivity, Radius & Fill Opacity)
        sliders_grid = QGridLayout()
        sliders_grid.setHorizontalSpacing(14)
        sliders_grid.setVerticalSpacing(8)

        # Eye Gaze Sensitivity
        sliders_grid.addWidget(QLabel("Eye Gaze Gain:"), 0, 0)
        self.gaze_gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gaze_gain_slider.setRange(8, 40)  # 0.8x ~ 4.0x
        self.gaze_gain_slider.setValue(18)     # 1.8x default
        self.gaze_gain_slider.valueChanged.connect(self._on_gain_changed)
        self.gaze_gain_lbl = QLabel("1.8x")
        self.gaze_gain_lbl.setProperty("class", "tally-value-mono")
        sliders_grid.addWidget(self.gaze_gain_slider, 0, 1)
        sliders_grid.addWidget(self.gaze_gain_lbl, 0, 2)

        # Reticle Radius
        sliders_grid.addWidget(QLabel("Reticle Radius:"), 1, 0)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(12, 60)
        self.size_slider.setValue(24)
        self.size_slider.valueChanged.connect(self._on_style_changed)
        self.size_val_lbl = QLabel("24 px")
        self.size_val_lbl.setProperty("class", "tally-value-mono")
        sliders_grid.addWidget(self.size_slider, 1, 1)
        sliders_grid.addWidget(self.size_val_lbl, 1, 2)

        # Reticle Fill Alpha
        sliders_grid.addWidget(QLabel("Fill Density:"), 2, 0)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 150)
        self.opacity_slider.setValue(60)
        self.opacity_slider.valueChanged.connect(self._on_style_changed)
        self.opacity_val_lbl = QLabel("60")
        self.opacity_val_lbl.setProperty("class", "tally-value-mono")
        sliders_grid.addWidget(self.opacity_slider, 2, 1)
        sliders_grid.addWidget(self.opacity_val_lbl, 2, 2)

        opt_layout.addLayout(sliders_grid)

        main_layout.addWidget(opt_card)

        # ---------------------------------------------------------
        # Bottom Utility Bar (Overlay Toggle & Minimization)
        # ---------------------------------------------------------
        bottom_bar = QHBoxLayout()
        self.hud_toggle_btn = QPushButton("HUD Overlay: Visible")
        self.hud_toggle_btn.clicked.connect(self._toggle_hud)
        bottom_bar.addWidget(self.hud_toggle_btn)

        main_layout.addLayout(bottom_bar)

    def _update_telemetry(self):
        connected = self.receiver.is_connected()
        self.live_indicator.set_active(connected)
        
        if connected:
            self.badge_text.setText(f"LIVE // {self.receiver.fps:.1f} FPS")
            self.badge_text.setStyleSheet("font-size: 11px; font-weight: 700; color: #10b981; letter-spacing: 0.5px;")
            self.fps_val.setText(f"{self.receiver.fps:.1f} FPS")
            self.fps_val.setStyleSheet("font-family: monospace; font-size: 20px; font-weight: 700; color: #34d399;")
        else:
            self.badge_text.setText("OFFLINE // WAITING")
            self.badge_text.setStyleSheet("font-size: 11px; font-weight: 700; color: #ef4444; letter-spacing: 0.5px;")
            self.fps_val.setText("0.0 FPS")
            self.fps_val.setStyleSheet("font-family: monospace; font-size: 20px; font-weight: 700; color: #6b7280;")

        self.packets_val.setText(f"{self.receiver.packet_count:,}")

        frame = self.receiver.get_latest_frame()
        if frame:
            hx, hy, hz = frame.head_pos
            self.head_vec_lbl.setText(f"Head: X:{hx:+.2f} Y:{hy:+.2f} Z:{hz:+.2f}m")
            
            # Gaze Signal display
            self.gaze_signal_lbl.setText(frame.raw_gaze_debug)
            if "NO EYE" in frame.raw_gaze_debug:
                self.gaze_signal_lbl.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 700;")
            else:
                self.gaze_signal_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 700;")

            # Raw packet snippet
            self.raw_packet_lbl.setText(f"Raw: {frame.raw_packet_debug}")
        else:
            self.gaze_signal_lbl.setText("Eye Signal: WAITING...")
            self.gaze_signal_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
            self.raw_packet_lbl.setText("Raw: [ Waiting for UDP stream... ]")

    def _start_calibration(self):
        # Open calibration window immediately without OS alert sound
        self.calib_win.start_calibration()

    def _on_calibration_finished(self, success: bool):
        if success:
            self.calib_status_badge.setText("[ ACTIVE MATRIX ]")
            self.calib_status_badge.setStyleSheet("font-family: monospace; font-size: 11px; font-weight: 700; color: #10b981;")
            self.calib_notice_lbl.setText("Matrix solved & saved successfully")
            self.calib_notice_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
        else:
            self.calib_status_badge.setText("[ DEFAULT PROJECTION ]")
            self.calib_status_badge.setStyleSheet("font-family: monospace; font-size: 11px; font-weight: 700; color: #f59e0b;")
            self.calib_notice_lbl.setText("Calibration aborted or incomplete")
            self.calib_notice_lbl.setStyleSheet("color: #f59e0b; font-size: 11px;")

    def _reset_calibration(self):
        self.calibrator.is_calibrated = False
        self.calibrator.poly_weights_x = None
        self.calibrator.poly_weights_y = None
        if os.path.exists(self.calibrator.save_path):
            try:
                os.remove(self.calibrator.save_path)
            except Exception:
                pass
        self.calib_status_badge.setText("[ DEFAULT PROJECTION ]")
        self.calib_status_badge.setStyleSheet("font-family: monospace; font-size: 11px; font-weight: 700; color: #f59e0b;")
        self.calib_notice_lbl.setText("Matrix reset to default model")
        self.calib_notice_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")

    def _on_style_changed(self):
        theme_name = self.color_combo.currentText()
        base_color = COLOR_THEMES.get(theme_name, QColor(0, 240, 255, 220))
        radius = float(self.size_slider.value())
        fill_alpha = int(self.opacity_slider.value())

        self.size_val_lbl.setText(f"{int(radius)} px")
        self.opacity_val_lbl.setText(f"{fill_alpha}")

        self.hud.set_pointer_style(radius, base_color, fill_alpha)

    def _on_gain_changed(self):
        gain_val = float(self.gaze_gain_slider.value()) / 10.0
        self.gaze_gain_lbl.setText(f"{gain_val:.1f}x")
        if self.geometry:
            self.geometry.set_gaze_gain(gain_val)

    def _on_smoothing_changed(self):
        preset_name = self.smooth_combo.currentText()
        min_cutoff, beta = FILTER_PRESETS.get(preset_name, (1.2, 0.04))
        self.hud.set_smoothing(min_cutoff, beta)

    def _toggle_hud(self):
        self.hud.hud_visible = not self.hud.hud_visible
        if self.hud.hud_visible:
            self.hud_toggle_btn.setText("HUD Overlay: Visible")
            self.hud.show()
        else:
            self.hud_toggle_btn.setText("HUD Overlay: Hidden")
            self.hud.hide()

    def _switch_port(self, new_port: int):
        self.receiver.restart_on_port(new_port)
        local_ip = get_local_ip()
        self.ip_display.setText(f"UDP Target: {local_ip}:{self.receiver.port}")

        self.btn_port_5005.setProperty("class", "tally-primary-btn" if new_port == 5005 else "")
        self.btn_port_ifacial.setProperty("class", "tally-primary-btn" if new_port == 49983 else "")
        self.btn_port_5005.setStyle(self.btn_port_5005.style())
        self.btn_port_ifacial.setStyle(self.btn_port_ifacial.style())

    def closeEvent(self, event):
        self.hud.close()
        self.calib_win.close()
        self.receiver.stop()
        super().closeEvent(event)
