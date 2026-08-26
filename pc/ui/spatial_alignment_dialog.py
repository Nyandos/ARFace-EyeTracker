import math
import numpy as np
from typing import Optional, List, Tuple
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QImage, QPixmap, QRadialGradient, QPolygonF
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QDoubleSpinBox, QFrame, QFileDialog, QSizePolicy
)
from core.pnp_solver import solve_monitor_pnp, MonitorSpatialPose
from core.geometry import GeometryEstimator

# Standard Display Dimensions (Width_m, Height_m)
MONITOR_PRESETS = {
    "24\" 16:9 (幅 53.1cm × 高 29.9cm)": (0.531, 0.299),
    "27\" 16:9 (幅 59.8cm × 高 33.6cm)": (0.598, 0.336),
    "32\" 16:9 (幅 70.8cm × 高 39.9cm)": (0.708, 0.399),
    "15.6\" ノートPC (幅 34.5cm × 高 19.4cm)": (0.345, 0.194),
}


class CornerInteractiveCanvas(QWidget):
    """
    Interactive image canvas with draggable corner handles to delineate the PC monitor.
    Handles: 0: Top-Left, 1: Top-Right, 2: Bottom-Right, 3: Bottom-Left
    """
    corners_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image: Optional[QImage] = None
        self.img_w = 1280
        self.img_h = 720

        # Normalized corners [0, 1]
        self.norm_corners = [
            QPointF(0.20, 0.20),  # Top-Left
            QPointF(0.80, 0.20),  # Top-Right
            QPointF(0.80, 0.75),  # Bottom-Right
            QPointF(0.20, 0.75),  # Bottom-Left
        ]
        self.dragging_idx = -1
        self.handle_radius = 12.0

    def set_image(self, img_arr: np.ndarray):
        """Set RGB numpy image"""
        h, w, c = img_arr.shape
        self.img_w = w
        self.img_h = h
        bytes_per_line = c * w
        self.image = QImage(img_arr.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        self.update()

    def set_placeholder_sample(self):
        """Create a clear illustrative placeholder canvas if no photo taken yet"""
        w, h = 1280, 720
        self.img_w = w
        self.img_h = h
        img = QImage(w, h, QImage.Format.Format_RGB888)
        img.fill(QColor(15, 23, 42))

        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw illustrative desk & monitor
        painter.setPen(QPen(QColor(30, 41, 59), 2))
        painter.setBrush(QBrush(QColor(11, 15, 23)))
        painter.drawRect(200, 100, 880, 480)

        painter.setPen(QColor(56, 189, 248))
        painter.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
        painter.drawText(200, 100, 880, 480, Qt.AlignmentFlag.AlignCenter, 
                         "[ モニター写真未受信 ]\n\nスマホの背面カメラでモニターを撮影するか、\nハンドルをドラッグして位置を調整してください")
        painter.end()

        self.image = img
        self.update()

    def get_pixel_corners(self) -> np.ndarray:
        pts = []
        for p in self.norm_corners:
            pts.append([p.x() * self.img_w, p.y() * self.img_h])
        return np.array(pts, dtype=np.float32)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            mpos = event.position()
            # Find nearest handle
            w_disp = self.width()
            h_disp = self.height()
            for idx, p in enumerate(self.norm_corners):
                screen_x = p.x() * w_disp
                screen_y = p.y() * h_disp
                dist = math.hypot(mpos.x() - screen_x, mpos.y() - screen_y)
                if dist <= self.handle_radius * 1.6:
                    self.dragging_idx = idx
                    return

    def mouseMoveEvent(self, event):
        if self.dragging_idx >= 0:
            mpos = event.position()
            nx = max(0.02, min(0.98, mpos.x() / self.width()))
            ny = max(0.02, min(0.98, mpos.y() / self.height()))
            self.norm_corners[self.dragging_idx] = QPointF(nx, ny)
            self.update()
            self.corners_changed.emit()

    def mouseReleaseEvent(self, event):
        self.dragging_idx = -1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w_disp = self.width()
        h_disp = self.height()

        # 1. Background image (scaled)
        if self.image:
            scaled = self.image.scaled(w_disp, h_disp, Qt.AspectRatioMode.IgnoreAspectRatio, 
                                       Qt.TransformationMode.SmoothTransformation)
            painter.drawImage(0, 0, scaled)
        else:
            painter.fillRect(0, 0, w_disp, h_disp, QColor(15, 23, 42))

        # 2. Polygon overlay connecting the 4 corners
        screen_pts = [QPointF(p.x() * w_disp, p.y() * h_disp) for p in self.norm_corners]
        poly = QPolygonF(screen_pts)

        # Semi-transparent emerald highlight
        painter.setPen(QPen(QColor(16, 185, 129, 220), 2.5))
        painter.setBrush(QBrush(QColor(16, 185, 129, 35)))
        painter.drawPolygon(poly)

        # 3. Corner Handles with Labels
        labels = ["TL (左上)", "TR (右上)", "BR (右下)", "BL (左下)"]
        for idx, pt in enumerate(screen_pts):
            # Outer ring
            painter.setPen(QPen(QColor(52, 211, 153), 2.0))
            painter.setBrush(QBrush(QColor(6, 78, 59, 210)))
            painter.drawEllipse(pt, self.handle_radius, self.handle_radius)

            # Center dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(249, 250, 251)))
            painter.drawEllipse(pt, 3.5, 3.5)

            # Label text badge
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            painter.setPen(QColor(243, 244, 246))
            offset_y = -18 if idx in (0, 1) else 24
            painter.drawText(int(pt.x() - 40), int(pt.y() + offset_y), 80, 18, 
                             Qt.AlignmentFlag.AlignCenter, labels[idx])


class Miniature3DSimulatorCanvas(QWidget):
    """
    Real-time 3D Isometric View simulating the physical spatial placement
    of the PC Monitor and iPhone in meters.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(320, 240)
        self.pose: Optional[MonitorSpatialPose] = None

    def set_pose(self, pose: Optional[MonitorSpatialPose]):
        self.pose = pose
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dark Card Background
        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor(17, 24, 39))

        # Title
        painter.setPen(QColor(156, 163, 175))
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.drawText(10, 20, "3D SPATIAL SIMULATOR (側面パース)")

        # Ground / Desk Line
        desk_y = int(h * 0.78)
        painter.setPen(QPen(QColor(31, 41, 55), 2))
        painter.drawLine(20, desk_y, w - 20, desk_y)
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(75, 85, 99))
        painter.drawText(22, desk_y + 16, "机 (Desk Plane)")

        if not self.pose:
            painter.setPen(QColor(107, 114, 128))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, "四隅を合わせると\n3D配置がシミュレートされます")
            return

        # -------------------------------------------------------------
        # 3D Side-View Projection:
        # Origin = Monitor Bottom Edge
        # -------------------------------------------------------------
        scale = 220.0  # pixels per meter

        mon_base_x = int(w * 0.35)
        mon_base_y = desk_y - 20  # Monitor raised on stand ~9cm
        mon_h_px = int(self.pose.monitor_height_m * scale)

        # Draw Monitor (Vertical Screen)
        painter.setPen(QPen(QColor(56, 189, 248), 4))
        painter.drawLine(mon_base_x, mon_base_y, mon_base_x, mon_base_y - mon_h_px)

        # Monitor Bezel & Stand
        painter.setPen(QPen(QColor(75, 85, 99), 2))
        painter.drawLine(mon_base_x, mon_base_y, mon_base_x, desk_y) # stand pole
        painter.drawLine(mon_base_x - 20, desk_y, mon_base_x + 20, desk_y) # stand base

        painter.setPen(QColor(56, 189, 248))
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        painter.drawText(mon_base_x - 65, mon_base_y - mon_h_px // 2, "PC MONITOR")

        # iPhone Position relative to Monitor Base:
        # pos_z_m: Depth in front (towards right in this 2D side-view)
        # pos_y_m: Height relative to bottom edge
        phone_x = int(mon_base_x + self.pose.pos_z_m * scale)
        phone_y = int(mon_base_y - self.pose.pos_y_m * scale)

        # Clamp safely within canvas
        phone_x = max(mon_base_x + 30, min(w - 30, phone_x))
        phone_y = max(mon_base_y - 40, min(desk_y - 4, phone_y))

        # iPhone Tilt Angle (Pitch)
        tilt_rad = math.radians(self.pose.pitch_deg)
        phone_len = 28.0
        # Tilted bar
        dx = phone_len * math.sin(tilt_rad)
        dy = -phone_len * math.cos(tilt_rad)

        painter.setPen(QPen(QColor(16, 185, 129), 5))
        painter.drawLine(int(phone_x - dx*0.5), int(phone_y - dy*0.5), 
                         int(phone_x + dx*0.5), int(phone_y + dy*0.5))

        # TrueDepth Eye-Tracking Ray (facing user towards right)
        ray_len = 45.0
        ray_dx = ray_len * math.cos(tilt_rad - 0.2)
        ray_dy = -ray_len * math.sin(tilt_rad - 0.2)
        painter.setPen(QPen(QColor(245, 158, 11, 200), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(phone_x, phone_y, int(phone_x + ray_dx), int(phone_y + ray_dy))

        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        painter.setPen(QColor(16, 185, 129))
        painter.drawText(phone_x - 20, phone_y - 20, "iPhone")


class SpatialAlignmentDialog(QDialog):
    """
    State-of-the-Art PnP Monitor Spatial Calibration Dialog (v4.0).
    Solves physical 3D positioning between PC monitor and iPhone via single monitor photo.
    """
    def __init__(self, geometry: GeometryEstimator, parent=None):
        super().__init__(parent)
        self.geometry = geometry
        self.solved_pose: Optional[MonitorSpatialPose] = None

        self.setWindowTitle("ARFace // 3D SPATIAL ALIGNMENT (PnP幾何測定)")
        self.resize(920, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0f17;
                color: #f3f4f6;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #e5e7eb;
            }
            QComboBox, QDoubleSpinBox {
                background-color: #111827;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px;
                color: #f3f4f6;
            }
            QPushButton {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                color: #e5e7eb;
            }
            QPushButton:hover {
                background-color: #374151;
                border-color: #4b5563;
            }
            QPushButton#applyBtn {
                background-color: #059669;
                border: 1px solid #10b981;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton#applyBtn:hover {
                background-color: #047857;
                border-color: #34d399;
            }
        """)

        self._init_ui()
        self.canvas.set_placeholder_sample()
        self._on_recalculate_pnp()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(18)

        # -------------------------------------------------------------
        # Left Column: Image Canvas & Capture Controls
        # -------------------------------------------------------------
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        left_title = QLabel("📷 モニター写真 ＆ 四隅アライメント")
        left_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;")
        left_col.addWidget(left_title)

        self.canvas = CornerInteractiveCanvas(self)
        self.canvas.corners_changed.connect(self._on_recalculate_pnp)
        left_col.addWidget(self.canvas, stretch=1)

        left_btns = QHBoxLayout()
        self.load_file_btn = QPushButton("📁 PCの画像ファイルを開く")
        self.load_file_btn.clicked.connect(self._on_open_file)
        self.sample_btn = QPushButton("🔄 サンプル画像で試す")
        self.sample_btn.clicked.connect(self._on_load_sample)
        left_btns.addWidget(self.load_file_btn)
        left_btns.addWidget(self.sample_btn)
        left_col.addLayout(left_btns)

        main_layout.addLayout(left_col, stretch=6)

        # -------------------------------------------------------------
        # Right Column: 3D Simulator, Metrics, and Apply
        # -------------------------------------------------------------
        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        # Section 1: Physical Size
        size_box = QFrame()
        size_box.setStyleSheet("background-color: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 10px;")
        size_layout = QVBoxLayout(size_box)
        size_layout.setSpacing(8)

        size_title = QLabel("📐 モニター物理サイズ設定")
        size_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #f3f4f6;")
        size_layout.addWidget(size_title)

        self.preset_combo = QComboBox()
        for name in MONITOR_PRESETS.keys():
            self.preset_combo.addItem(name)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        size_layout.addWidget(self.preset_combo)

        dim_row = QHBoxLayout()
        dim_row.addWidget(QLabel("幅 (cm):"))
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(20.0, 150.0)
        self.width_spin.setValue(53.1)
        self.width_spin.valueChanged.connect(self._on_recalculate_pnp)
        dim_row.addWidget(self.width_spin)

        dim_row.addWidget(QLabel("高 (cm):"))
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(10.0, 100.0)
        self.height_spin.setValue(29.9)
        self.height_spin.valueChanged.connect(self._on_recalculate_pnp)
        dim_row.addWidget(self.height_spin)
        size_layout.addLayout(dim_row)

        right_col.addWidget(size_box)

        # Section 2: 3D Miniature Simulator Canvas
        self.sim_canvas = Miniature3DSimulatorCanvas(self)
        right_col.addWidget(self.sim_canvas)

        # Section 3: Calculated Metrics Badge
        self.metrics_card = QFrame()
        self.metrics_card.setStyleSheet("background-color: #161f30; border: 1px solid #0284c7; border-radius: 8px; padding: 12px;")
        metrics_layout = QVBoxLayout(self.metrics_card)
        metrics_layout.setSpacing(4)

        metrics_lbl = QLabel("PnP 3D空間測定結果")
        metrics_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #38bdf8;")
        self.metric_res_lbl = QLabel("計算中...")
        self.metric_res_lbl.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; color: #f9fafb; font-weight: 600;")
        self.metric_res_lbl.setWordWrap(True)

        metrics_layout.addWidget(metrics_lbl)
        metrics_layout.addWidget(self.metric_res_lbl)
        right_col.addWidget(self.metrics_card)

        # Apply Button
        self.apply_btn = QPushButton("✓ 空間配置を幾何エンジンに適用")
        self.apply_btn.setObjectName("applyBtn")
        self.apply_btn.clicked.connect(self._on_apply)
        right_col.addWidget(self.apply_btn)

        right_col.addStretch()
        main_layout.addLayout(right_col, stretch=4)

    def feed_photo(self, img_arr: np.ndarray):
        """Called when photo is received over HTTP from iPhone"""
        self.canvas.set_image(img_arr)
        self._on_recalculate_pnp()
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_preset_changed(self, text: str):
        if text in MONITOR_PRESETS:
            w_m, h_m = MONITOR_PRESETS[text]
            self.width_spin.blockSignals(True)
            self.height_spin.blockSignals(True)
            self.width_spin.setValue(w_m * 100.0)
            self.height_spin.setValue(h_m * 100.0)
            self.width_spin.blockSignals(False)
            self.height_spin.blockSignals(False)
            self._on_recalculate_pnp()

    def _on_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "モニター写真を開く", "", "Image Files (*.jpg *.jpeg *.png *.bmp)"
        )
        if file_path:
            import cv2
            img_bgr = cv2.imread(file_path)
            if img_bgr is not None:
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                self.canvas.set_image(img_rgb)
                self._on_recalculate_pnp()

    def _on_load_sample(self):
        self.canvas.set_placeholder_sample()
        self._on_recalculate_pnp()

    def _on_recalculate_pnp(self):
        corners = self.canvas.get_pixel_corners()
        w_m = self.width_spin.value() / 100.0
        h_m = self.height_spin.value() / 100.0

        pose = solve_monitor_pnp(
            corners_2d=corners,
            monitor_w_m=w_m,
            monitor_h_m=h_m,
            img_w=self.canvas.img_w,
            img_h=self.canvas.img_h,
            fov_deg=65.0
        )
        self.solved_pose = pose
        self.sim_canvas.set_pose(pose)

        if pose:
            self.metric_res_lbl.setText(
                f"• 下端から下: {abs(pose.pos_y_m)*100.0:.1f} cm\n"
                f"• 画面から手前: {pose.pos_z_m*100.0:.1f} cm\n"
                f"• 左右オフセット: {pose.pos_x_m*100.0:+.1f} cm\n"
                f"• iPhone仰角: {pose.pitch_deg:.1f}°"
            )
        else:
            self.metric_res_lbl.setText("四隅の形状が異常です。各角を正しく指定してください。")

    def _on_apply(self):
        if self.solved_pose:
            # Inject into geometry engine
            self.geometry.set_physical_monitor_pose(
                pos_x_m=self.solved_pose.pos_x_m,
                pos_y_m=self.solved_pose.pos_y_m,
                pos_z_m=self.solved_pose.pos_z_m,
                pitch_deg=self.solved_pose.pitch_deg,
                monitor_w_m=self.solved_pose.monitor_width_m,
                monitor_h_m=self.solved_pose.monitor_height_m
            )
            print(f"[SpatialAlignment] Applied: {self.solved_pose.describe()}")
            self.accept()
