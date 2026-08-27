import sys
import os
import math
import socket
import numpy as np
from typing import Optional, List, Tuple, Dict
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QSlider, QComboBox, QFrame, QTabWidget, QProgressBar, QScrollArea
)
from core.receiver import UDPReceiver
from core.calibrator import Calibrator
from core.geometry import GeometryEstimator
from .hud_overlay import HUDOverlay
from .calib_window import CalibrationWindow
from .face_preview import FacePreviewWidget
from .spatial_alignment_dialog import SpatialAlignmentDialog
from .face_simulator_window import FaceSimulatorWindow
from core.photo_receiver import PhotoReceiver

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

/* Tabs */
QTabWidget::pane {
    border: 1px solid #1f2937;
    background-color: #0b0f17;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background-color: #111827;
    color: #9ca3af;
    border: 1px solid #1f2937;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background-color: #161f30;
    color: #38bdf8;
    border-color: #38bdf8;
    border-bottom: 2px solid #38bdf8;
}
QTabBar::tab:hover:!selected {
    background-color: #1f2937;
    color: #f3f4f6;
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
    padding: 6px 14px;
    min-height: 32px;
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

/* Primary Action Button (Blue) */
QPushButton.tally-primary-btn {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
    color: #ffffff;
}
QPushButton.tally-primary-btn:hover {
    background-color: #0369a1;
    border-color: #7dd3fc;
}

/* Accent Action (Emerald / 9-Point Calib) */
QPushButton.tally-accent-btn {
    background-color: #059669;
    border: 1px solid #34d399;
    color: #ffffff;
    font-weight: 700;
}
QPushButton.tally-accent-btn:hover {
    background-color: #047857;
    border-color: #6ee7b7;
}

/* Teal Button (Active Mouse) */
QPushButton.tally-teal-btn {
    background-color: #0f766e;
    border: 1px solid #2dd4bf;
    color: #ffffff;
    font-weight: 700;
}
QPushButton.tally-teal-btn:hover {
    background-color: #115e59;
    border-color: #5eead4;
}

/* Purple Button (3D Spatial Alignment) */
QPushButton.tally-purple-btn {
    background-color: #2e1065;
    border: 1px solid #8b5cf6;
    color: #ede9fe;
    font-weight: 700;
}
QPushButton.tally-purple-btn:hover {
    background-color: #3b0764;
    border-color: #a78bfa;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #1f2937;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #0284c7;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #f9fafb;
    border: 2px solid #0284c7;
    width: 16px;
    height: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
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
    padding: 4px 10px;
    min-height: 28px;
    color: #f3f4f6;
    font-weight: 500;
    font-size: 11px;
}
QComboBox:hover {
    border-color: #4b5563;
}
QComboBox:focus {
    border-color: #38bdf8;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #111827;
    border: 1px solid #374151;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
    color: #f3f4f6;
    padding: 4px;
}

/* Scroll Area */
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    background: #0b0f17;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #1f2937;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #374151;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
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
    """Minimalist LED Pulse Indicator"""
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
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(1, 1, 8, 8)


class ControlPanel(QMainWindow):
    """
    Hallmark 'Tally' Control Center with 3D Face Wireframe & Data Debug Inspector.
    """
    def __init__(self, receiver: UDPReceiver, calibrator: Calibrator, hud: HUDOverlay, calib_win: CalibrationWindow, geometry: Optional[GeometryEstimator] = None):
        super().__init__()
        self.receiver = receiver
        self.calibrator = calibrator
        self.hud = hud
        self.calib_win = calib_win
        self.geometry = geometry or calibrator.geometry

        self.setWindowTitle("ARFace-Eyetracker — Control Center")
        self.resize(680, 920)
        self.setMinimumSize(600, 720)
        self.setStyleSheet(TALLY_STYLE)

        self._init_ui()

        # Photo & Sensor Receiver Server for PnP Spatial Calibration
        self.photo_receiver = PhotoReceiver(port=5006)
        self.photo_receiver.photo_received.connect(self._on_photo_received)
        self.photo_receiver.sensor_data_received.connect(self._on_sensor_data_received)
        self.photo_receiver.start()
        self.spatial_dialog: Optional[SpatialAlignmentDialog] = None
        self.sim_dialog: Optional[FaceSimulatorWindow] = None

        # Signals
        self.calib_win.calibration_finished.connect(self._on_calibration_finished)

        # 30Hz Telemetry & Inspector Polling (smooth 3D wireframe animation)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_telemetry)
        self.status_timer.start(33)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # ---------------------------------------------------------
        # Header Bar
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
        self.badge_frame.setMinimumWidth(160)
        self.badge_frame.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 14px;
                padding: 2px 8px;
            }
        """)
        badge_layout = QHBoxLayout(self.badge_frame)
        badge_layout.setContentsMargins(10, 4, 12, 4)
        badge_layout.setSpacing(8)
        
        self.live_indicator = LiveIndicator()
        self.badge_text = QLabel("STANDBY")
        self.badge_text.setStyleSheet("font-size: 11px; font-weight: 700; color: #9ca3af; letter-spacing: 0.8px;")
        badge_layout.addWidget(self.live_indicator)
        badge_layout.addWidget(self.badge_text)
        header_bar.addWidget(self.badge_frame)

        main_layout.addLayout(header_bar)

        # ---------------------------------------------------------
        # Tab Widget Container
        # ---------------------------------------------------------
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Build Tabs
        self._init_tab_controls()
        self._init_tab_inspector()

        # ---------------------------------------------------------
        # Bottom Utility Bar (Overlay Toggle & Status)
        # ---------------------------------------------------------
        bottom_bar = QHBoxLayout()
        self.hud_toggle_btn = QPushButton("HUD Overlay: Visible")
        self.hud_toggle_btn.clicked.connect(self._toggle_hud)
        bottom_bar.addWidget(self.hud_toggle_btn)

        main_layout.addLayout(bottom_bar)

    def _init_tab_controls(self):
        """Tab 1: Main Controls, Calibration, HUD Display Settings"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 1. Telemetry Ingest Card
        feed_card = QFrame()
        feed_card.setProperty("class", "tally-card")
        feed_layout = QVBoxLayout(feed_card)
        feed_layout.setSpacing(8)

        feed_head = QHBoxLayout()
        feed_title = QLabel("INGEST ENDPOINT")
        feed_title.setProperty("class", "tally-section-title")
        local_ip = get_local_ip()
        self.ip_display = QLabel(f"UDP Target: {local_ip}:{self.receiver.port}")
        self.ip_display.setStyleSheet("font-family: monospace; font-size: 11px; color: #38bdf8;")
        feed_head.addWidget(feed_title)
        feed_head.addStretch()
        feed_head.addWidget(self.ip_display)
        feed_layout.addLayout(feed_head)

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

        # Metric Columns (FPS Rate, Total Packets)
        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(10)

        # Box 1: FPS Rate
        b1 = QFrame()
        b1.setProperty("class", "tally-card-elevated")
        b1_l = QVBoxLayout(b1)
        b1_l.setContentsMargins(10, 8, 10, 8)
        b1_lbl = QLabel("STREAM RATE")
        b1_lbl.setProperty("class", "tally-section-title")
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
        b2_lbl = QLabel("PACKETS INGESTED")
        b2_lbl.setProperty("class", "tally-section-title")
        self.packets_val = QLabel("0")
        self.packets_val.setProperty("class", "tally-metric-large")
        b2_l.addWidget(b2_lbl)
        b2_l.addWidget(self.packets_val)
        metrics_grid.addWidget(b2, 0, 1)

        feed_layout.addLayout(metrics_grid)
        layout.addWidget(feed_card)

        # 2. Calibration Section
        calib_card = QFrame()
        calib_card.setProperty("class", "tally-card")
        calib_layout = QVBoxLayout(calib_card)
        calib_layout.setSpacing(10)

        calib_head = QHBoxLayout()
        calib_title = QLabel("3D SPATIAL CALIBRATION")
        calib_title.setProperty("class", "tally-section-title")
        self.calib_status_badge = QLabel("[ ACTIVE MATRIX ]" if self.calibrator.is_calibrated else "[ DEFAULT PROJECTION ]")
        self.calib_status_badge.setStyleSheet("font-family: monospace; font-size: 11px; font-weight: 700; color: #10b981;" if self.calibrator.is_calibrated else "font-family: monospace; font-size: 11px; font-weight: 700; color: #f59e0b;")
        calib_head.addWidget(calib_title)
        calib_head.addStretch()
        calib_head.addWidget(self.calib_status_badge)
        calib_layout.addLayout(calib_head)

        calib_desc = QLabel("【9点静止メッシュ】四隅・端・中央を各0.8秒注視して誤差0写像（推奨・約10秒）\n【ACTIVE MOUSE】マウスを自由に見つめて10秒間で即座に微調整・最適化")
        calib_desc.setStyleSheet("color: #9ca3af; font-size: 11px; margin-bottom: 2px;")
        calib_desc.setWordWrap(True)
        calib_layout.addWidget(calib_desc)

        calib_btns = QHBoxLayout()
        self.start_calib_btn = QPushButton("🎯 9-POINT MESH (10s)")
        self.start_calib_btn.setProperty("class", "tally-accent-btn")
        self.start_calib_btn.clicked.connect(self._start_calibration)

        self.active_mouse_btn = QPushButton("🖱️ ACTIVE MOUSE (10s)")
        self.active_mouse_btn.setProperty("class", "tally-teal-btn")
        self.active_mouse_btn.clicked.connect(self._start_active_mouse_calibration)

        self.reset_calib_btn = QPushButton("Reset")
        self.reset_calib_btn.clicked.connect(self._reset_calibration)

        calib_btns.addWidget(self.start_calib_btn, stretch=5)
        calib_btns.addWidget(self.active_mouse_btn, stretch=5)
        calib_btns.addWidget(self.reset_calib_btn, stretch=2)
        calib_layout.addLayout(calib_btns)

        pnp_btn_row = QHBoxLayout()
        self.pnp_spatial_btn = QPushButton("📐 3D SPATIAL ALIGNMENT (写真測定)")
        self.pnp_spatial_btn.setProperty("class", "tally-purple-btn")
        self.pnp_spatial_btn.clicked.connect(self._open_spatial_alignment_dialog)
        pnp_btn_row.addWidget(self.pnp_spatial_btn, stretch=3)

        self.tab1_sim_btn = QPushButton("🎭 3D SIMULATOR (仮想動作)")
        self.tab1_sim_btn.setProperty("class", "tally-teal-btn")
        self.tab1_sim_btn.clicked.connect(self._open_face_simulator)
        pnp_btn_row.addWidget(self.tab1_sim_btn, stretch=2)

        calib_layout.addLayout(pnp_btn_row)

        # Head-Gaze Hybrid Boost Slider
        boost_row = QHBoxLayout()
        boost_lbl = QLabel("首振り端部ブースト (Extended Reach):")
        boost_lbl.setStyleSheet("color: #d1d5db; font-size: 11px;")
        self.boost_val_lbl = QLabel(f"{int(self.calibrator.hybrid_boost_gain * 100)}%")
        self.boost_val_lbl.setProperty("class", "tally-value-mono")

        self.boost_slider = QSlider(Qt.Orientation.Horizontal)
        self.boost_slider.setRange(0, 200)
        self.boost_slider.setValue(int(self.calibrator.hybrid_boost_gain * 100))
        self.boost_slider.valueChanged.connect(self._on_boost_slider_changed)

        boost_row.addWidget(boost_lbl)
        boost_row.addWidget(self.boost_slider, stretch=1)
        boost_row.addWidget(self.boost_val_lbl)
        calib_layout.addLayout(boost_row)

        self.calib_notice_lbl = QLabel("Matrix loaded from calibration_data.json" if self.calibrator.is_calibrated else "No calibration profile active")
        self.calib_notice_lbl.setStyleSheet("color: #6b7280; font-size: 10px;")
        calib_layout.addWidget(self.calib_notice_lbl)

        layout.addWidget(calib_card)

        # 3. HUD Customization Options
        opt_card = QFrame()
        opt_card.setProperty("class", "tally-card")
        opt_layout = QVBoxLayout(opt_card)
        opt_layout.setSpacing(10)

        opt_title = QLabel("HUD OVERLAY & FILTER OPTICS")
        opt_title.setProperty("class", "tally-section-title")
        opt_layout.addWidget(opt_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        # Reticle Color
        grid.addWidget(QLabel("Color Theme:"), 0, 0)
        self.color_combo = QComboBox()
        for name in COLOR_THEMES.keys():
            self.color_combo.addItem(name)
        self.color_combo.currentTextChanged.connect(self._on_style_changed)
        grid.addWidget(self.color_combo, 0, 1, 1, 2)

        # Smoothing Preset (1€ Filter)
        grid.addWidget(QLabel("Smoothing (1€):"), 1, 0)
        self.smooth_combo = QComboBox()
        for preset in FILTER_PRESETS.keys():
            self.smooth_combo.addItem(preset)
        self.smooth_combo.currentTextChanged.connect(self._on_smoothing_changed)
        grid.addWidget(self.smooth_combo, 1, 1, 1, 2)

        # Gaze Gain Slider
        grid.addWidget(QLabel("Gaze Gain:"), 2, 0)
        self.gaze_gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gaze_gain_slider.setRange(5, 30)
        self.gaze_gain_slider.setValue(10)
        self.gaze_gain_slider.valueChanged.connect(self._on_gain_changed)
        self.gaze_gain_lbl = QLabel("1.0x")
        self.gaze_gain_lbl.setProperty("class", "tally-value-mono")
        grid.addWidget(self.gaze_gain_slider, 2, 1)
        grid.addWidget(self.gaze_gain_lbl, 2, 2)

        # Reticle Size Slider
        grid.addWidget(QLabel("Reticle Radius:"), 3, 0)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(10, 60)
        self.size_slider.setValue(24)
        self.size_slider.valueChanged.connect(self._on_style_changed)
        self.size_val_lbl = QLabel("24 px")
        self.size_val_lbl.setProperty("class", "tally-value-mono")
        grid.addWidget(self.size_slider, 3, 1)
        grid.addWidget(self.size_val_lbl, 3, 2)

        # Fill Opacity Slider
        grid.addWidget(QLabel("Fill Opacity:"), 4, 0)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 150)
        self.opacity_slider.setValue(45)
        self.opacity_slider.valueChanged.connect(self._on_style_changed)
        self.opacity_val_lbl = QLabel("45")
        self.opacity_val_lbl.setProperty("class", "tally-value-mono")
        grid.addWidget(self.opacity_slider, 4, 1)
        grid.addWidget(self.opacity_val_lbl, 4, 2)

        opt_layout.addLayout(grid)
        layout.addWidget(opt_card)

        layout.addStretch()
        scroll.setWidget(tab_widget)
        self.tabs.addTab(scroll, "🎛️ CONTROLS && CALIB")

    def _init_tab_inspector(self):
        """Tab 2: 3D Face Wireframe Preview & Full Data Debug Inspector"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Top Section: 3D Wireframe Face Widget
        self.face_preview = FacePreviewWidget()
        self.face_preview.setFixedHeight(230)
        layout.addWidget(self.face_preview)

        # Simulator Launch Button
        sim_btn_row = QHBoxLayout()
        self.tab2_sim_btn = QPushButton("🎭 3D FACE MOTION SIMULATOR (仮想顔デバッガ起動)")
        self.tab2_sim_btn.setProperty("class", "tally-purple-btn")
        self.tab2_sim_btn.clicked.connect(self._open_face_simulator)
        sim_btn_row.addWidget(self.tab2_sim_btn)
        layout.addLayout(sim_btn_row)

        # Bottom Section: Data Debug Telemetry Card
        debug_card = QFrame()
        debug_card.setProperty("class", "tally-card")
        debug_layout = QVBoxLayout(debug_card)
        debug_layout.setSpacing(8)

        dbg_title = QLabel("PACKET & SIGNAL TELEMETRY INSPECTOR")
        dbg_title.setProperty("class", "tally-section-title")
        debug_layout.addWidget(dbg_title)

        dbg_grid = QGridLayout()
        dbg_grid.setHorizontalSpacing(10)
        dbg_grid.setVerticalSpacing(6)

        # Row 0: Protocol & Packet Size
        dbg_grid.addWidget(QLabel("Format:"), 0, 0)
        self.dbg_format_lbl = QLabel("Awaiting...")
        self.dbg_format_lbl.setStyleSheet("font-family: monospace; color: #38bdf8; font-weight: bold;")
        dbg_grid.addWidget(self.dbg_format_lbl, 0, 1)

        dbg_grid.addWidget(QLabel("Packet Size:"), 0, 2)
        self.dbg_pktsize_lbl = QLabel("0 Bytes")
        self.dbg_pktsize_lbl.setProperty("class", "tally-value-mono")
        dbg_grid.addWidget(self.dbg_pktsize_lbl, 0, 3)

        # Row 1: FPS Rate & Frame Jitter
        dbg_grid.addWidget(QLabel("Frame Rate:"), 1, 0)
        self.dbg_fps_lbl = QLabel("0.0 FPS")
        self.dbg_fps_lbl.setStyleSheet("font-family: monospace; color: #34d399; font-weight: bold;")
        dbg_grid.addWidget(self.dbg_fps_lbl, 1, 1)

        dbg_grid.addWidget(QLabel("Frame Jitter:"), 1, 2)
        self.dbg_jitter_lbl = QLabel("0.0 ms")
        self.dbg_jitter_lbl.setProperty("class", "tally-value-mono")
        dbg_grid.addWidget(self.dbg_jitter_lbl, 1, 3)

        # Row 2: Head Position (X, Y, Z cm)
        dbg_grid.addWidget(QLabel("Head Pos:"), 2, 0)
        self.dbg_headpos_lbl = QLabel("X: 0.0  Y: 0.0  Z: 0.0 cm")
        self.dbg_headpos_lbl.setProperty("class", "tally-value-mono")
        dbg_grid.addWidget(self.dbg_headpos_lbl, 2, 1, 1, 3)

        # Row 3: Head Rotation (Pitch, Yaw, Roll deg)
        dbg_grid.addWidget(QLabel("Head Rotation:"), 3, 0)
        self.dbg_headrot_lbl = QLabel("P: +0.0°  Y: +0.0°  R: +0.0°")
        self.dbg_headrot_lbl.setProperty("class", "tally-value-mono")
        dbg_grid.addWidget(self.dbg_headrot_lbl, 3, 1, 1, 3)

        # Row 4: Gaze Signal / LookAt
        dbg_grid.addWidget(QLabel("Eye Signal:"), 4, 0)
        self.dbg_gaze_lbl = QLabel("Waiting...")
        self.dbg_gaze_lbl.setStyleSheet("font-family: monospace; color: #34d399;")
        dbg_grid.addWidget(self.dbg_gaze_lbl, 4, 1, 1, 3)

        # Row 5: Blinks Left & Right
        dbg_grid.addWidget(QLabel("Blink Left:"), 5, 0)
        self.dbg_blink_l_lbl = QLabel("0.00")
        self.dbg_blink_l_lbl.setProperty("class", "tally-value-mono")
        dbg_grid.addWidget(self.dbg_blink_l_lbl, 5, 1)

        dbg_grid.addWidget(QLabel("Blink Right:"), 5, 2)
        self.dbg_blink_r_lbl = QLabel("0.00")
        self.dbg_blink_r_lbl.setProperty("class", "tally-value-mono")
        dbg_grid.addWidget(self.dbg_blink_r_lbl, 5, 3)

        debug_layout.addLayout(dbg_grid)

        # Raw Packet Snippet Box
        raw_box = QFrame()
        raw_box.setProperty("class", "tally-card-elevated")
        raw_layout = QVBoxLayout(raw_box)
        raw_layout.setContentsMargins(10, 6, 10, 6)
        raw_lbl = QLabel("RAW PACKET SNIPPET")
        raw_lbl.setProperty("class", "tally-section-title")
        self.raw_packet_lbl = QLabel("[ No UDP packet ingested yet ]")
        self.raw_packet_lbl.setStyleSheet("font-family: monospace; font-size: 11px; color: #9ca3af;")
        self.raw_packet_lbl.setWordWrap(True)
        raw_layout.addWidget(raw_lbl)
        raw_layout.addWidget(self.raw_packet_lbl)
        debug_layout.addWidget(raw_box)

        layout.addWidget(debug_card)
        layout.addStretch()

        scroll.setWidget(tab_widget)
        self.tabs.addTab(scroll, "👤 3D FACE && DATA DEBUG")

    def _update_telemetry(self):
        connected = self.receiver.is_connected()
        self.live_indicator.set_active(connected)
        fps = self.receiver.fps

        if connected:
            self.badge_text.setText(f"LIVE // {fps:.1f} FPS")
            self.badge_text.setStyleSheet("font-size: 11px; font-weight: 700; color: #10b981; letter-spacing: 0.5px;")
            self.fps_val.setText(f"{fps:.1f} FPS")
            self.fps_val.setStyleSheet("font-family: monospace; font-size: 20px; font-weight: 700; color: #34d399;")
        else:
            self.badge_text.setText("OFFLINE // WAITING")
            self.badge_text.setStyleSheet("font-size: 11px; font-weight: 700; color: #ef4444; letter-spacing: 0.5px;")
            self.fps_val.setText("0.0 FPS")
            self.fps_val.setStyleSheet("font-family: monospace; font-size: 20px; font-weight: 700; color: #6b7280;")

        self.packets_val.setText(f"{self.receiver.packet_count:,}")

        frame = self.receiver.get_latest_frame()
        # Feed frame to 3D Wireframe Preview
        self.face_preview.update_frame(frame)

        if frame:
            hx, hy, hz = frame.head_pos
            # Debug Inspector updates
            self.dbg_format_lbl.setText("Fast Binary (ARF1 84B)" if self.receiver.last_packet_size == 84 else "Raw JSON Stream")
            self.dbg_pktsize_lbl.setText(f"{self.receiver.last_packet_size} Bytes")
            self.dbg_fps_lbl.setText(f"{fps:.1f} FPS")
            self.dbg_jitter_lbl.setText(f"{self.receiver.jitter_ms:.1f} ms")

            self.dbg_headpos_lbl.setText(f"X:{hx*100:+.1f}  Y:{hy*100:+.1f}  Z:{hz*100:+.1f} cm")

            # Extract Euler angles for display
            qx, qy, qz, qw = frame.head_rot
            sinr = 2 * (qw * qx + qy * qz)
            cosr = 1 - 2 * (qx * qx + qy * qy)
            roll = math.degrees(math.atan2(sinr, cosr))

            sinp = 2 * (qw * qy - qz * qx)
            sinp = max(-1.0, min(1.0, sinp))
            pitch = math.degrees(math.asin(sinp))

            siny = 2 * (qw * qz + qx * qy)
            cosy = 1 - 2 * (qy * qy + qz * qz)
            yaw = math.degrees(math.atan2(siny, cosy))

            self.dbg_headrot_lbl.setText(f"Pitch:{pitch:+.1f}°  Yaw:{yaw:+.1f}°  Roll:{roll:+.1f}°")
            self.dbg_gaze_lbl.setText(frame.raw_gaze_debug)

            self.dbg_blink_l_lbl.setText(f"{frame.blink_left:.2f}")
            self.dbg_blink_r_lbl.setText(f"{frame.blink_right:.2f}")

            self.raw_packet_lbl.setText(f"Header: {frame.raw_packet_debug} | LookAt: [{frame.look_at_point[0]:.2f}, {frame.look_at_point[1]:.2f}]m")
        else:
            self.dbg_format_lbl.setText("Awaiting UDP feed...")
            self.dbg_pktsize_lbl.setText("0 Bytes")
            self.dbg_fps_lbl.setText("0.0 FPS")
            self.dbg_jitter_lbl.setText("0.0 ms")
            self.dbg_headpos_lbl.setText("X: 0.0  Y: 0.0  Z: 0.0 cm")
            self.dbg_headrot_lbl.setText("P: +0.0°  Y: +0.0°  R: +0.0°")
            self.dbg_gaze_lbl.setText("Waiting for stream...")
            self.raw_packet_lbl.setText("[ No UDP packet ingested yet ]")

    def _start_calibration(self):
        self.calib_win.start_calibration()

    def _start_active_mouse_calibration(self):
        self.calib_win.start_active_mouse_calibration()

    def _open_spatial_alignment_dialog(self):
        if not self.spatial_dialog:
            self.spatial_dialog = SpatialAlignmentDialog(self.geometry, self)
        self.spatial_dialog.show()
        self.spatial_dialog.raise_()
        self.spatial_dialog.activateWindow()

    def _open_face_simulator(self):
        if not self.sim_dialog:
            port = self.receiver.port
            self.sim_dialog = FaceSimulatorWindow(receiver=self.receiver, target_port=port, parent=self)
        self.sim_dialog.show()
        self.sim_dialog.raise_()
        self.sim_dialog.activateWindow()

    def _on_photo_received(self, img_arr: np.ndarray):
        if not self.spatial_dialog:
            self.spatial_dialog = SpatialAlignmentDialog(self.geometry, self)
        self.spatial_dialog.feed_photo(img_arr)

    def _on_sensor_data_received(self, data: dict):
        m_pitch = float(data.get("monitor_pitch_deg", 90.0))
        p_pitch = float(data.get("phone_pitch_deg", 25.0))
        b_tilt = data.get("monitor_back_tilt_deg")
        p_tilt = data.get("phone_upward_tilt_deg")
        rel_angle = float(data.get("relative_angle_deg", abs(m_pitch - p_pitch)))

        self.geometry.set_sensor_lab_angles(
            monitor_pitch_deg=m_pitch,
            phone_pitch_deg=p_pitch,
            monitor_back_tilt_deg=b_tilt,
            phone_upward_tilt_deg=p_tilt,
            relative_angle_deg=rel_angle
        )
        tilt_str = f"+{b_tilt:.1f}°" if b_tilt is not None and b_tilt >= 0 else f"{b_tilt:.1f}°" if b_tilt is not None else f"{90.0-m_pitch:.1f}°"
        phone_tilt_str = f"{p_tilt:.1f}°" if p_tilt is not None else f"{p_pitch:.1f}°"
        self.calib_notice_lbl.setText(f"📐 センサー同期完了: モニター後傾 {tilt_str} | iPhone仰角 {phone_tilt_str} (交差 {rel_angle:.1f}°)")
        self.calib_notice_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700;")

    def closeEvent(self, event):
        if hasattr(self, 'photo_receiver') and self.photo_receiver:
            self.photo_receiver.stop()
        if hasattr(self, 'sim_dialog') and self.sim_dialog:
            self.sim_dialog.close()
        super().closeEvent(event)

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

    def _on_boost_slider_changed(self, value: int):
        self.calibrator.hybrid_boost_gain = value / 100.0
        self.boost_val_lbl.setText(f"{value}%")
        self.calibrator.save()

    def _reset_calibration(self):
        self.calibrator.is_calibrated = False
        self.calibrator.anchor_gaze_centers = None
        self.calibrator.anchor_screen_pts = None
        self.calibrator.triangle_affines = None
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
        min_cutoff, beta = FILTER_PRESETS.get(preset_name, (0.4, 0.008))
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
