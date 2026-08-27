import sys
import math
import time
import socket
import numpy as np
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QComboBox, QGroupBox, QGridLayout, QScrollArea, QFrame,
    QStackedWidget
)

from core.protocol import ARFaceFrame, pack_binary_frame
from core.receiver import UDPReceiver
from ui.face_preview import FacePreviewWidget

VISUALIZER_STYLE = """
QDialog {
    background-color: #0b0f17;
    color: #f9fafb;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
QFrame.sim-card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 12px;
}
QLabel {
    color: #e5e7eb;
    font-size: 12px;
}
QLabel.sim-section-title {
    color: #38bdf8;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.0px;
}
QLabel.sim-val-mono {
    font-family: monospace;
    font-size: 13px;
    font-weight: 700;
    color: #34d399;
    min-width: 60px;
}
QLabel.sim-badge-live {
    font-family: monospace;
    font-size: 11px;
    font-weight: 800;
    color: #10b981;
    background-color: #064e3b;
    border: 1px solid #059669;
    border-radius: 12px;
    padding: 3px 10px;
}
QLabel.sim-badge-sim {
    font-family: monospace;
    font-size: 11px;
    font-weight: 800;
    color: #c084fc;
    background-color: #3b0764;
    border: 1px solid #9333ea;
    border-radius: 12px;
    padding: 3px 10px;
}
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
    background: #38bdf8;
    border: 1px solid #7dd3fc;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #f0f9ff;
}
QPushButton.sim-tab-active {
    background-color: #0284c7;
    color: #ffffff;
    border: 1px solid #38bdf8;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 700;
    min-height: 32px;
    padding: 4px 14px;
}
QPushButton.sim-tab-inactive {
    background-color: #1f2937;
    color: #9ca3af;
    border: 1px solid #374151;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    min-height: 32px;
    padding: 4px 14px;
}
QPushButton.sim-tab-inactive:hover {
    background-color: #374151;
    color: #f3f4f6;
}
QPushButton.sim-btn-secondary {
    background-color: #1f2937;
    color: #9ca3af;
    border: 1px solid #374151;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    min-height: 28px;
    padding: 2px 10px;
}
QPushButton.sim-btn-secondary:hover {
    background-color: #374151;
    color: #f3f4f6;
}
QComboBox {
    background-color: #111827;
    color: #f9fafb;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
    min-height: 28px;
}
"""

class FaceSimulatorWindow(QDialog):
    """
    3D Face Visualizer & Motion Simulator Inspector Window.
    Provides a large, dedicated 3D visualization showing exactly how the user's face,
    head orientation, distance, and gaze vectors are being tracked in real time.
    Also supports virtual simulation mode with manual sliders and auto patterns.
    """
    def __init__(self, receiver: Optional[UDPReceiver] = None, target_port: int = 5009, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.receiver = receiver
        self.target_port = target_port
        self.setWindowTitle("3D Face Motion Visualizer // ARFace Inspector")
        self.resize(640, 840)
        self.setMinimumSize(540, 700)
        self.setStyleSheet(VISUALIZER_STYLE)

        # Mode: 'live' (render actual incoming iPhone stream) or 'sim' (synthetic simulator)
        self.current_mode = "live"

        # UDP Sender Socket for Virtual Simulation
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.target_ip = "127.0.0.1"

        # Synthetic Simulator State
        self.head_yaw_deg = 0.0
        self.head_pitch_deg = 0.0
        self.head_roll_deg = 0.0
        self.head_x_cm = 0.0
        self.head_y_cm = 0.0
        self.head_z_cm = 45.0
        self.gaze_yaw_deg = 0.0
        self.gaze_pitch_deg = 0.0
        self.blink_left = 0.0
        self.blink_right = 0.0
        self.auto_mode = "manual"
        self.anim_time = 0.0

        self._init_ui()

        # 60Hz Render & Update Loop
        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self._on_tick)
        self.loop_timer.start(16)  # ~60 FPS

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # -------------------------------------------------------------
        # Header: Mode Switcher Tabs & Status Badge
        # -------------------------------------------------------------
        header = QHBoxLayout()

        # Mode Switch Buttons
        self.btn_live_mode = QPushButton("📡 リアルタイム顔認識 (LIVE)")
        self.btn_live_mode.setProperty("class", "sim-tab-active")
        self.btn_live_mode.clicked.connect(lambda: self._set_mode("live"))
        header.addWidget(self.btn_live_mode)

        self.btn_sim_mode = QPushButton("🧪 仮想シミュレータ (SIM)")
        self.btn_sim_mode.setProperty("class", "sim-tab-inactive")
        self.btn_sim_mode.clicked.connect(lambda: self._set_mode("sim"))
        header.addWidget(self.btn_sim_mode)

        header.addStretch()

        self.badge_status = QLabel("● LIVE FEED")
        self.badge_status.setProperty("class", "sim-badge-live")
        header.addWidget(self.badge_status)

        main_layout.addLayout(header)

        # -------------------------------------------------------------
        # Center: Large High-Resolution 3D Face Wireframe Widget
        # -------------------------------------------------------------
        self.face_preview = FacePreviewWidget()
        self.face_preview.setFixedHeight(340)
        main_layout.addWidget(self.face_preview)

        # -------------------------------------------------------------
        # Bottom: Stacked Widget (Page 0: Live Telemetry / Page 1: Simulator Sliders)
        # -------------------------------------------------------------
        self.stack = QStackedWidget()

        # Page 0: Live Telemetry Inspector
        page_live = self._build_live_telemetry_page()
        self.stack.addWidget(page_live)

        # Page 1: Virtual Simulator Sliders
        page_sim = self._build_simulator_controls_page()
        self.stack.addWidget(page_sim)

        main_layout.addWidget(self.stack, stretch=1)

    def _build_live_telemetry_page(self) -> QWidget:
        card = QFrame()
        card.setProperty("class", "sim-card")
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        title = QLabel("TRACKED FACE & GAZE METRICS (リアルタイム認識データ)")
        title.setProperty("class", "sim-section-title")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        # 1. Head Pose (Euler)
        grid.addWidget(QLabel("首の向き (Head Pose):"), 0, 0)
        self.live_pose_lbl = QLabel("P: +0.0°  Y: +0.0°  R: +0.0°")
        self.live_pose_lbl.setProperty("class", "sim-val-mono")
        grid.addWidget(self.live_pose_lbl, 0, 1)

        # 2. Distance & 3D Position
        grid.addWidget(QLabel("顔の距離・位置 (3D Position):"), 1, 0)
        self.live_pos_lbl = QLabel("距離: 0.0cm (X: 0.0, Y: 0.0)")
        self.live_pos_lbl.setProperty("class", "sim-val-mono")
        grid.addWidget(self.live_pos_lbl, 1, 1)

        # 3. Gaze Vector
        grid.addWidget(QLabel("視線レイ (Eye Gaze):"), 2, 0)
        self.live_gaze_lbl = QLabel("Yaw: +0.0°  Pitch: +0.0°")
        self.live_gaze_lbl.setProperty("class", "sim-val-mono")
        grid.addWidget(self.live_gaze_lbl, 2, 1)

        # 4. Blinks
        grid.addWidget(QLabel("瞬き (Blink L / R):"), 3, 0)
        self.live_blink_lbl = QLabel("L: 0.00 (開)   R: 0.00 (開)")
        self.live_blink_lbl.setProperty("class", "sim-val-mono")
        grid.addWidget(self.live_blink_lbl, 3, 1)

        # 5. Stream Health
        grid.addWidget(QLabel("ストリーム状態 (Feed):"), 4, 0)
        self.live_fps_lbl = QLabel("0.0 FPS // 0 packets")
        self.live_fps_lbl.setProperty("class", "sim-val-mono")
        grid.addWidget(self.live_fps_lbl, 4, 1)

        layout.addLayout(grid)

        notice_lbl = QLabel("※ iPhoneから受信中の「顔の向き・首振り・視線・瞬き」を忠実に3D空間で描画しています。")
        notice_lbl.setStyleSheet("color: #6b7280; font-size: 11px; margin-top: 4px;")
        layout.addWidget(notice_lbl)

        layout.addStretch()
        return card

    def _build_simulator_controls_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Preset Patterns Card
        preset_card = QFrame()
        preset_card.setProperty("class", "sim-card")
        p_layout = QVBoxLayout(preset_card)
        p_layout.setSpacing(8)

        p_title = QLabel("仮想アニメーションパターン")
        p_title.setProperty("class", "sim-section-title")
        p_layout.addWidget(p_title)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🛑 Manual Sliders (自由手動操作)", "manual")
        self.mode_combo.addItem("♾️ Smooth Figure-8 Scan (8の字全画面スキャン)", "figure8")
        self.mode_combo.addItem("↔️ Head Shake & Decouple (左右首振りスイング)", "swing")
        self.mode_combo.addItem("🎯 9-Point Auto Gaze (9点校正ポイント自動注視)", "9point")
        self.mode_combo.currentIndexChanged.connect(self._on_sim_mode_changed)
        p_layout.addWidget(self.mode_combo)

        reset_btn = QPushButton("↺ 直立中心にリセット")
        reset_btn.setProperty("class", "sim-btn-secondary")
        reset_btn.clicked.connect(self.reset_to_neutral)
        p_layout.addWidget(reset_btn)
        layout.addWidget(preset_card)

        # Head Rotation Sliders
        rot_card = QFrame()
        rot_card.setProperty("class", "sim-card")
        r_layout = QVBoxLayout(rot_card)
        r_layout.setSpacing(6)
        r_title = QLabel("首の回転 (HEAD ROTATION)")
        r_title.setProperty("class", "sim-section-title")
        r_layout.addWidget(r_title)

        grid_r = QGridLayout()
        grid_r.setHorizontalSpacing(10)
        grid_r.setVerticalSpacing(4)

        grid_r.addWidget(QLabel("Yaw (左右):"), 0, 0)
        self.yaw_slider = QSlider(Qt.Orientation.Horizontal)
        self.yaw_slider.setRange(-45, 45)
        self.yaw_slider.setValue(0)
        self.yaw_slider.valueChanged.connect(self._on_slider_changed)
        grid_r.addWidget(self.yaw_slider, 0, 1)
        self.yaw_val_lbl = QLabel("0.0°")
        self.yaw_val_lbl.setProperty("class", "sim-val-mono")
        grid_r.addWidget(self.yaw_val_lbl, 0, 2)

        grid_r.addWidget(QLabel("Pitch (上下):"), 1, 0)
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-30, 30)
        self.pitch_slider.setValue(0)
        self.pitch_slider.valueChanged.connect(self._on_slider_changed)
        grid_r.addWidget(self.pitch_slider, 1, 1)
        self.pitch_val_lbl = QLabel("0.0°")
        self.pitch_val_lbl.setProperty("class", "sim-val-mono")
        grid_r.addWidget(self.pitch_val_lbl, 1, 2)

        grid_r.addWidget(QLabel("Roll (傾げ):"), 2, 0)
        self.roll_slider = QSlider(Qt.Orientation.Horizontal)
        self.roll_slider.setRange(-25, 25)
        self.roll_slider.setValue(0)
        self.roll_slider.valueChanged.connect(self._on_slider_changed)
        grid_r.addWidget(self.roll_slider, 2, 1)
        self.roll_val_lbl = QLabel("0.0°")
        self.roll_val_lbl.setProperty("class", "sim-val-mono")
        grid_r.addWidget(self.roll_val_lbl, 2, 2)

        r_layout.addLayout(grid_r)
        layout.addWidget(rot_card)

        # Eye Gaze Sliders
        gaze_card = QFrame()
        gaze_card.setProperty("class", "sim-card")
        g_layout = QVBoxLayout(gaze_card)
        g_layout.setSpacing(6)
        g_title = QLabel("視線方向 (EYE GAZE)")
        g_title.setProperty("class", "sim-section-title")
        g_layout.addWidget(g_title)

        grid_g = QGridLayout()
        grid_g.setHorizontalSpacing(10)
        grid_g.setVerticalSpacing(4)

        grid_g.addWidget(QLabel("Gaze Yaw:"), 0, 0)
        self.gaze_yaw_slider = QSlider(Qt.Orientation.Horizontal)
        self.gaze_yaw_slider.setRange(-35, 35)
        self.gaze_yaw_slider.setValue(0)
        self.gaze_yaw_slider.valueChanged.connect(self._on_slider_changed)
        grid_g.addWidget(self.gaze_yaw_slider, 0, 1)
        self.gaze_yaw_lbl = QLabel("0.0°")
        self.gaze_yaw_lbl.setProperty("class", "sim-val-mono")
        grid_g.addWidget(self.gaze_yaw_lbl, 0, 2)

        grid_g.addWidget(QLabel("Gaze Pitch:"), 1, 0)
        self.gaze_pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.gaze_pitch_slider.setRange(-25, 25)
        self.gaze_pitch_slider.setValue(0)
        self.gaze_pitch_slider.valueChanged.connect(self._on_slider_changed)
        grid_g.addWidget(self.gaze_pitch_slider, 1, 1)
        self.gaze_pitch_lbl = QLabel("0.0°")
        self.gaze_pitch_lbl.setProperty("class", "sim-val-mono")
        grid_g.addWidget(self.gaze_pitch_lbl, 1, 2)

        g_layout.addLayout(grid_g)
        layout.addWidget(gaze_card)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _set_mode(self, mode: str):
        self.current_mode = mode
        if mode == "live":
            self.btn_live_mode.setProperty("class", "sim-tab-active")
            self.btn_sim_mode.setProperty("class", "sim-tab-inactive")
            self.badge_status.setText("● LIVE FEED")
            self.badge_status.setProperty("class", "sim-badge-live")
            self.stack.setCurrentIndex(0)
        else:
            self.btn_live_mode.setProperty("class", "sim-tab-inactive")
            self.btn_sim_mode.setProperty("class", "sim-tab-active")
            self.badge_status.setText("🧪 VIRTUAL SIMULATOR")
            self.badge_status.setProperty("class", "sim-badge-sim")
            self.stack.setCurrentIndex(1)

        self.btn_live_mode.style().unpolish(self.btn_live_mode)
        self.btn_live_mode.style().polish(self.btn_live_mode)
        self.btn_sim_mode.style().unpolish(self.btn_sim_mode)
        self.btn_sim_mode.style().polish(self.btn_sim_mode)
        self.badge_status.style().unpolish(self.badge_status)
        self.badge_status.style().polish(self.badge_status)

    def _on_sim_mode_changed(self):
        self.auto_mode = self.mode_combo.currentData()

    def reset_to_neutral(self):
        self.mode_combo.setCurrentIndex(0)
        self.yaw_slider.setValue(0)
        self.pitch_slider.setValue(0)
        self.roll_slider.setValue(0)
        self.gaze_yaw_slider.setValue(0)
        self.gaze_pitch_slider.setValue(0)

    def _on_slider_changed(self):
        if self.auto_mode != "manual":
            self.mode_combo.setCurrentIndex(0)

        self.head_yaw_deg = float(self.yaw_slider.value())
        self.head_pitch_deg = float(self.pitch_slider.value())
        self.head_roll_deg = float(self.roll_slider.value())
        self.gaze_yaw_deg = float(self.gaze_yaw_slider.value())
        self.gaze_pitch_deg = float(self.gaze_pitch_slider.value())

        self.yaw_val_lbl.setText(f"{self.head_yaw_deg:+.1f}°")
        self.pitch_val_lbl.setText(f"{self.head_pitch_deg:+.1f}°")
        self.roll_val_lbl.setText(f"{self.head_roll_deg:+.1f}°")
        self.gaze_yaw_lbl.setText(f"{self.gaze_yaw_deg:+.1f}°")
        self.gaze_pitch_lbl.setText(f"{self.gaze_pitch_deg:+.1f}°")

    def _on_tick(self):
        if self.current_mode == "live":
            # 1. LIVE MODE: Fetch real frame from receiver
            frame = self.receiver.get_latest_frame() if self.receiver else None
            self.face_preview.update_frame(frame)

            if frame:
                # Extract Euler
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

                hx, hy, hz = frame.head_pos
                dist_cm = hz * 100.0

                self.live_pose_lbl.setText(f"Pitch: {pitch:+.1f}°  Yaw: {yaw:+.1f}°  Roll: {roll:+.1f}°")
                self.live_pos_lbl.setText(f"距離: {dist_cm:.1f}cm (X: {hx*100:+.1f}, Y: {hy*100:+.1f})")

                # Gaze
                gx, gy, gz = frame.left_gaze
                g_yaw = math.degrees(math.atan2(gx, -gz))
                g_pitch = math.degrees(math.atan2(gy, -gz))
                self.live_gaze_lbl.setText(f"Yaw: {g_yaw:+.1f}°  Pitch: {g_pitch:+.1f}°")

                # Blinks
                bl = frame.blink_left
                br = frame.blink_right
                bl_str = "閉" if bl > 0.6 else "開"
                br_str = "閉" if br > 0.6 else "開"
                self.live_blink_lbl.setText(f"左: {bl:.2f} ({bl_str})   右: {br:.2f} ({br_str})")

                fps = self.receiver.fps if self.receiver else 0.0
                pkts = self.receiver.packet_count if self.receiver else 0
                self.live_fps_lbl.setText(f"{fps:.1f} FPS // {pkts:,} パケット受信")
            else:
                self.live_pose_lbl.setText("待機中 (UDPフィード受信待ち)")
                self.live_pos_lbl.setText("距離: 0.0cm")
                self.live_gaze_lbl.setText("Yaw: 0.0°  Pitch: 0.0°")
                self.live_blink_lbl.setText("左: 0.00   右: 0.00")
                self.live_fps_lbl.setText("0.0 FPS // 0 packets")

        else:
            # 2. SIMULATOR MODE: Generate synthetic frame
            self.anim_time += 0.016
            if self.auto_mode == "figure8":
                t = self.anim_time * 1.5
                self.head_yaw_deg = math.sin(t) * 18.0
                self.head_pitch_deg = math.sin(t * 2.0) * 10.0
                self.gaze_yaw_deg = math.sin(t) * 22.0
                self.gaze_pitch_deg = math.sin(t * 2.0) * 14.0
                self._sync_sliders_silent()
            elif self.auto_mode == "swing":
                t = self.anim_time * 2.0
                self.head_yaw_deg = math.sin(t) * 25.0
                self.head_pitch_deg = math.cos(t * 0.5) * 5.0
                self.gaze_yaw_deg = -self.head_yaw_deg * 0.7
                self._sync_sliders_silent()
            elif self.auto_mode == "9point":
                idx = int(self.anim_time * 0.8) % 9
                grid_xs = [-22.0, 0.0, 22.0, -22.0, 0.0, 22.0, -22.0, 0.0, 22.0]
                grid_ys = [-14.0, -14.0, -14.0, 0.0, 0.0, 0.0, 14.0, 14.0, 14.0]
                self.gaze_yaw_deg = grid_xs[idx]
                self.gaze_pitch_deg = grid_ys[idx]
                self.head_yaw_deg = grid_xs[idx] * 0.3
                self.head_pitch_deg = grid_ys[idx] * 0.3
                self._sync_sliders_silent()

            frame = self._build_sim_frame()
            self.face_preview.update_frame(frame)

            # Transmit via UDP
            try:
                packet_bytes = pack_binary_frame(frame)
                self.sock.sendto(packet_bytes, (self.target_ip, self.target_port))
            except Exception:
                pass

    def _sync_sliders_silent(self):
        self.yaw_slider.blockSignals(True)
        self.pitch_slider.blockSignals(True)
        self.gaze_yaw_slider.blockSignals(True)
        self.gaze_pitch_slider.blockSignals(True)

        self.yaw_slider.setValue(int(self.head_yaw_deg))
        self.pitch_slider.setValue(int(self.head_pitch_deg))
        self.gaze_yaw_slider.setValue(int(self.gaze_yaw_deg))
        self.gaze_pitch_slider.setValue(int(self.gaze_pitch_deg))

        self.yaw_slider.blockSignals(False)
        self.pitch_slider.blockSignals(False)
        self.gaze_yaw_slider.blockSignals(False)
        self.gaze_pitch_slider.blockSignals(False)

        self.yaw_val_lbl.setText(f"{self.head_yaw_deg:+.1f}°")
        self.pitch_val_lbl.setText(f"{self.head_pitch_deg:+.1f}°")
        self.gaze_yaw_lbl.setText(f"{self.gaze_yaw_deg:+.1f}°")
        self.gaze_pitch_lbl.setText(f"{self.gaze_pitch_deg:+.1f}°")

    def _build_sim_frame(self) -> ARFaceFrame:
        now = time.time()
        pos = np.array([self.head_x_cm / 100.0, self.head_y_cm / 100.0, self.head_z_cm / 100.0], dtype=np.float32)

        r_yaw = math.radians(self.head_yaw_deg)
        r_pitch = math.radians(self.head_pitch_deg)
        r_roll = math.radians(self.head_roll_deg)

        cy = math.cos(r_yaw * 0.5)
        sy = math.sin(r_yaw * 0.5)
        cp = math.cos(r_pitch * 0.5)
        sp = math.sin(r_pitch * 0.5)
        cr = math.cos(r_roll * 0.5)
        sr = math.sin(r_roll * 0.5)

        qw = cr * cp * cy + sr * sp * sy
        qx = sr * cp * cy - cr * sp * sy
        qy = cr * sp * cy + sr * cp * sy
        qz = cr * cp * sy - sr * sp * cy

        rot = np.array([qx, qy, qz, qw], dtype=np.float32)

        gy = math.radians(self.gaze_yaw_deg)
        gp = math.radians(self.gaze_pitch_deg)
        g_vx = math.sin(gy)
        g_vy = math.sin(gp)
        g_vz = -math.sqrt(max(0.001, 1.0 - g_vx*g_vx - g_vy*g_vy))
        gaze_ray = np.array([g_vx, g_vy, g_vz], dtype=np.float32)
        look_at = np.array([g_vx * 0.45, g_vy * 0.45, 0.0], dtype=np.float32)

        return ARFaceFrame(
            timestamp=now,
            head_pos=pos,
            head_rot=rot,
            left_gaze=gaze_ray,
            right_gaze=gaze_ray,
            look_at_point=look_at,
            blink_left=float(self.blink_left),
            blink_right=float(self.blink_right),
            raw_packet_debug="SIM_ARF1_60HZ",
            raw_gaze_debug=f"Sim Gaze: Y:{self.gaze_yaw_deg:+.1f}° P:{self.gaze_pitch_deg:+.1f}°"
        )

    def closeEvent(self, event):
        self.loop_timer.stop()
        try:
            self.sock.close()
        except Exception:
            pass
        super().closeEvent(event)
