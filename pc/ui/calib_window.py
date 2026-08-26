import time
from typing import List, Tuple
from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import QWidget
from core.calibrator import Calibrator, CalibTarget
from core.protocol import ARFaceFrame

class CalibrationWindow(QWidget):
    """
    Hallmark 'Tally' Multi-Dimensional 3D Calibration Interface.
    Guides the user through natural grid sampling and head-pose decoupling.
    """
    calibration_finished = pyqtSignal(bool)

    def __init__(self, calibrator: Calibrator, screen_width: int = 1920, screen_height: int = 1080):
        super().__init__()
        self.calibrator = calibrator
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.targets: List[CalibTarget] = []
        self.current_idx = 0
        self.point_start_time = 0.0
        self.is_active = False

        self._init_window()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)

    def _init_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setGeometry(0, 0, self.screen_width, self.screen_height)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def start_calibration(self):
        self.targets = self.calibrator.get_multi_pose_targets(self.screen_width, self.screen_height)
        self.calibrator.reset_samples(self.targets)
        self.current_idx = 0
        self.point_start_time = time.perf_counter()
        self.is_active = True

        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.timer.start(16)

    def handle_frame(self, frame: ARFaceFrame):
        if not self.is_active or self.current_idx >= len(self.targets):
            return
        # Allow 0.25s for user to settle gaze
        elapsed = time.perf_counter() - self.point_start_time
        if elapsed >= 0.25:
            self.calibrator.add_sample(self.current_idx, frame)

    def _on_tick(self):
        if not self.is_active or self.current_idx >= len(self.targets):
            return

        target = self.targets[self.current_idx]
        now = time.perf_counter()
        elapsed = now - self.point_start_time

        if elapsed >= target.duration:
            self.current_idx += 1
            if self.current_idx >= len(self.targets):
                self.is_active = False
                self.timer.stop()
                success = self.calibrator.fit()
                self.hide()
                self.calibration_finished.emit(success)
                return
            else:
                self.point_start_time = now

        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.is_active = False
            self.timer.stop()
            self.hide()
            self.calibration_finished.emit(False)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        if not self.is_active or self.current_idx >= len(self.targets):
            return

        target = self.targets[self.current_idx]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Dark matte background
        painter.fillRect(0, 0, self.screen_width, self.screen_height, QColor(11, 15, 23, 240))

        # 2. Stage Badge & Step Counter
        header_y = int(self.screen_height * 0.08)

        painter.setPen(QColor(56, 189, 248))
        font_stage = QFont("Consolas", 11, QFont.Weight.Bold)
        painter.setFont(font_stage)
        stage_str = f"// {target.stage_name} [{self.current_idx + 1:02d} / {len(self.targets):02d}]"
        painter.drawText(0, header_y - 24, self.screen_width, 24, Qt.AlignmentFlag.AlignHCenter, stage_str)

        # 3. Dynamic Action Instruction (High-Contrast Bold)
        painter.setPen(QColor(249, 250, 251))
        font_inst = QFont("Segoe UI", 16, QFont.Weight.Bold)
        painter.setFont(font_inst)
        painter.drawText(0, header_y + 4, self.screen_width, 36, Qt.AlignmentFlag.AlignHCenter, target.instruction)

        painter.setPen(QColor(156, 163, 175))
        font_sub = QFont("Segoe UI", 11)
        painter.setFont(font_sub)
        painter.drawText(0, header_y + 42, self.screen_width, 24, Qt.AlignmentFlag.AlignHCenter, "(ESC to cancel calibration)")

        # 4. Precision Reticle
        tx, ty = target.screen_pos
        now = time.perf_counter()
        elapsed = now - self.point_start_time
        progress = min(1.0, max(0.0, elapsed / target.duration))

        base_r = 34.0
        active_r = base_r * (1.0 - 0.75 * progress)

        # Crosshair Ticks
        painter.setPen(QPen(QColor(75, 85, 99), 1.2))
        tick_dist = base_r + 8
        tick_len = 6
        painter.drawLine(QPointF(tx, ty - tick_dist), QPointF(tx, ty - tick_dist - tick_len))
        painter.drawLine(QPointF(tx, ty + tick_dist), QPointF(tx, ty + tick_dist + tick_len))
        painter.drawLine(QPointF(tx - tick_dist, ty), QPointF(tx - tick_dist - tick_len, ty))
        painter.drawLine(QPointF(tx + tick_dist, ty), QPointF(tx + tick_dist + tick_len, ty))

        # Static outer boundary
        painter.setPen(QPen(QColor(55, 65, 81), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(tx, ty), base_r, base_r)

        # Active countdown ring (Cyan #38BDF8)
        painter.setPen(QPen(QColor(56, 189, 248), 2.2))
        painter.drawEllipse(QPointF(tx, ty), active_r, active_r)

        # Sharp center pin
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(249, 250, 251)))
        painter.drawEllipse(QPointF(tx, ty), 3.5, 3.5)
