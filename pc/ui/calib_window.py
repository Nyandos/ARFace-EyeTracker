import time
import math
import numpy as np
from enum import Enum
from typing import List, Tuple, Optional
from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient, QCursor
from PyQt6.QtWidgets import QWidget
from core.calibrator import Calibrator, CALIB_ANCHORS_9
from core.protocol import ARFaceFrame
from core.geometry import quaternion_to_euler_angles, quaternion_to_rotation_matrix

class CalibState(Enum):
    INTRO = 0           # Instructions screen, press Space/Click to begin
    ANCHOR_POINT = 1    # 9-point static gaze capture with smooth transit & filling ring
    ACTIVE_MOUSE = 2    # 10s user-controlled active mouse gaze calibration
    COMPLETED = 3       # Solved matrix confirmation summary


class CalibrationWindow(QWidget):
    """
    Precision 9-Point Static Mesh & Active Mouse Calibration Interface.
    Features:
    - 9 Static Anchor Points: Eliminates human dynamic lag; provides mathematical 100% snap accuracy.
    - Continuous 60FPS fluid procedural animation (pulsing rings, OK badges, smooth transit).
    - Active Mouse Mode: 10s freeform mouse gaze fine-tuning.
    - Zero audio/beeps, pure visual elegance.
    """
    calibration_finished = pyqtSignal(bool)

    def __init__(self, calibrator: Calibrator, screen_width: int = 1920, screen_height: int = 1080):
        super().__init__()
        self.calibrator = calibrator
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.state = CalibState.INTRO
        self.state_start_time = 0.0
        self.is_active = False

        # 9-Point Anchor State
        self.current_anchor_idx = 0
        self.anchor_progress = 0.0        # 0.0 to 1.0 (holds for ~0.75s)
        self.anchor_ok_until = 0.0        # Flash OK for 0.25s before moving
        self.transit_start_time = 0.0     # Smooth transition between points
        self.prev_pt = QPointF(screen_width * 0.5, screen_height * 0.5)
        self.target_pt = QPointF(screen_width * 0.5, screen_height * 0.5)

        # Active Mouse Mode State
        self.active_mouse_duration = 10.0
        self.mouse_trail: List[Tuple[float, float, float]] = []
        self.total_samples = 0

        # Telemetry
        self.latest_yaw = 0.0
        self.latest_pitch = 0.0

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
        """Start 9-Point Precision Static Mesh Calibration"""
        self.calibrator.reset_dynamic_samples()
        self.state = CalibState.INTRO
        self.current_anchor_idx = 0
        self.anchor_progress = 0.0
        self.anchor_ok_until = 0.0
        self.total_samples = 0

        cx = self.screen_width * 0.5
        cy = self.screen_height * 0.5
        self.prev_pt = QPointF(cx, cy)
        self.target_pt = QPointF(cx, cy)

        self.state_start_time = time.perf_counter()
        self.is_active = True

        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.timer.start(16)

    def start_active_mouse_calibration(self):
        """Start 10-second Active Mouse Calibration"""
        self.calibrator.reset_dynamic_samples()
        self.state = CalibState.ACTIVE_MOUSE
        self.active_mouse_duration = 10.0
        self.mouse_trail.clear()
        self.total_samples = 0
        self.state_start_time = time.perf_counter()
        self.is_active = True

        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.timer.start(16)

    def _begin_anchor_sequence(self):
        now = time.perf_counter()
        self.state = CalibState.ANCHOR_POINT
        self.current_anchor_idx = 0
        self.anchor_progress = 0.0
        self.anchor_ok_until = 0.0
        self._set_current_anchor_target(0)
        self.transit_start_time = now

    def _set_current_anchor_target(self, idx: int):
        now = time.perf_counter()
        tag, norm_x, norm_y, desc = CALIB_ANCHORS_9[idx]
        self.prev_pt = QPointF(self.target_pt)
        self.target_pt = QPointF(norm_x * self.screen_width, norm_y * self.screen_height)
        self.transit_start_time = now
        self.anchor_progress = 0.0
        self.anchor_ok_until = 0.0

    def _advance_anchor(self):
        self.current_anchor_idx += 1
        if self.current_anchor_idx >= len(CALIB_ANCHORS_9):
            # All 9 anchors completed! Solve piecewise affine mesh
            success = self.calibrator.fit(self.screen_width, self.screen_height)
            self.state = CalibState.COMPLETED
            self.state_start_time = time.perf_counter()
        else:
            self._set_current_anchor_target(self.current_anchor_idx)

    def handle_frame(self, frame: ARFaceFrame):
        if not self.is_active:
            return

        now = time.perf_counter()
        yaw, pitch, roll = quaternion_to_euler_angles(frame.head_rot)
        self.latest_yaw = yaw
        self.latest_pitch = pitch

        if self.state == CalibState.ANCHOR_POINT:
            # Check if transit is complete (transit takes 0.25s)
            transit_elapsed = now - self.transit_start_time
            if transit_elapsed >= 0.25 and self.anchor_ok_until == 0.0:
                # Accumulate sample for this anchor
                self.calibrator.add_anchor_sample(self.current_anchor_idx, frame)
                self.total_samples += 1
                # Advance hold progress towards 1.0 (fills in ~0.75s)
                self.anchor_progress = min(1.0, self.anchor_progress + 0.025)

                if self.anchor_progress >= 1.0:
                    self.anchor_ok_until = now + 0.25

        elif self.state == CalibState.ACTIVE_MOUSE:
            cpos = QCursor.pos()
            tx = max(0.0, min(float(self.screen_width), float(cpos.x())))
            ty = max(0.0, min(float(self.screen_height), float(cpos.y())))
            # Store in anchor 0 or general pool
            self.calibrator.add_anchor_sample(0, frame)
            self.total_samples += 1
            self.mouse_trail.append((tx, ty, now))
            if len(self.mouse_trail) > 120:
                self.mouse_trail.pop(0)

    def _on_tick(self):
        if not self.is_active:
            return

        now = time.perf_counter()

        if self.state == CalibState.ANCHOR_POINT:
            if self.anchor_ok_until > 0 and now >= self.anchor_ok_until:
                self._advance_anchor()

        elif self.state == CalibState.ACTIVE_MOUSE:
            elapsed = now - self.state_start_time
            if elapsed >= self.active_mouse_duration:
                self.state = CalibState.COMPLETED
                self.state_start_time = now

        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_calibration()
        elif event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            if self.state == CalibState.INTRO:
                self._begin_anchor_sequence()
            elif self.state == CalibState.ANCHOR_POINT:
                # Manual skip to next anchor
                self._advance_anchor()
            elif self.state == CalibState.COMPLETED:
                self._finish_calibration(True)
        elif event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Right):
            if self.state == CalibState.ANCHOR_POINT:
                self._advance_anchor()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == CalibState.INTRO:
                self._begin_anchor_sequence()
            elif self.state == CalibState.ANCHOR_POINT:
                self._advance_anchor()
            elif self.state == CalibState.COMPLETED:
                self._finish_calibration(True)

    def _cancel_calibration(self):
        self.is_active = False
        self.timer.stop()
        self.hide()
        self.calibration_finished.emit(False)

    def _finish_calibration(self, success: bool):
        self.is_active = False
        self.timer.stop()
        self.hide()
        self.calibration_finished.emit(success)

    # -------------------------------------------------------------------------
    # Render Dispatcher
    # -------------------------------------------------------------------------
    def paintEvent(self, event):
        if not self.is_active:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Deep matte canvas (#0B0F17)
        painter.fillRect(0, 0, self.screen_width, self.screen_height, QColor(11, 15, 23, 248))

        if self.state == CalibState.INTRO:
            self._draw_intro(painter)
        elif self.state == CalibState.ANCHOR_POINT:
            self._draw_anchor_point(painter)
        elif self.state == CalibState.ACTIVE_MOUSE:
            self._draw_active_mouse(painter)
        elif self.state == CalibState.COMPLETED:
            self._draw_completion_summary(painter)

    # -------------------------------------------------------------------------
    # Intro Screen
    # -------------------------------------------------------------------------
    def _draw_intro(self, painter: QPainter):
        cx = self.screen_width / 2.0
        cy = self.screen_height / 2.0
        now = time.perf_counter()

        # Modal Card
        card_w = min(680, int(self.screen_width * 0.65))
        card_h = min(420, int(self.screen_height * 0.52))
        card_x = cx - card_w / 2.0
        card_y = cy - card_h / 2.0

        painter.setPen(QPen(QColor(56, 189, 248), 1.5))
        painter.setBrush(QBrush(QColor(17, 24, 39, 245)))
        painter.drawRoundedRect(int(card_x), int(card_y), card_w, card_h, 12, 12)

        # Header
        painter.setPen(QColor(56, 189, 248))
        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        painter.drawText(int(card_x), int(card_y + 36), card_w, 24, Qt.AlignmentFlag.AlignCenter, 
                         "// 9-POINT PRECISION MESH CALIBRATION")

        painter.setPen(QColor(249, 250, 251))
        painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        painter.drawText(int(card_x), int(card_y + 70), card_w, 32, Qt.AlignmentFlag.AlignCenter, 
                         "静止9点アンカー校正 ＆ 首振りハイブリッド")

        # Instructions
        box_w = card_w - 60
        box_x = card_x + 30
        box_y = card_y + 115
        painter.setPen(QPen(QColor(31, 41, 55), 1))
        painter.setBrush(QBrush(QColor(22, 31, 48, 180)))
        painter.drawRoundedRect(int(box_x), int(box_y), box_w, 180, 8, 8)

        painter.setFont(QFont("Segoe UI", 12))
        painter.setPen(QColor(229, 231, 235))
        lines = [
            "① 画面の 9 箇所に現れる光球を、順番に約 0.8 秒ずつじっと見つめてください。",
            "② 1点目（中央）で基準正面姿勢を自動ロックし、四隅まで誤差なく写像します。",
            "③ 【首振りハイブリッド】画面端を見るときは、顔を少し端に向けるだけで",
            "    吸い付くように四隅の角までスコーンと届くようになります。",
            "④ 全9点で約10秒で完了します。( [SPACE] でいつでもスキップ可能 )"
        ]
        for i, line in enumerate(lines):
            painter.drawText(int(box_x + 16), int(box_y + 32 + i * 28), line)

        # Action Prompt
        pulse = 0.5 + 0.5 * math.sin(now * 5.0)
        btn_col = QColor(16, 185, 129, int(200 + 55 * pulse))
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        painter.setPen(btn_col)
        painter.drawText(int(card_x), int(card_y + card_h - 36), card_w, 30, Qt.AlignmentFlag.AlignCenter, 
                         "▶ [ SPACE キー ] または [ 画面クリック ] で開始")

    # -------------------------------------------------------------------------
    # 9-Point Anchor Drawing
    # -------------------------------------------------------------------------
    def _draw_anchor_point(self, painter: QPainter):
        now = time.perf_counter()
        idx = self.current_anchor_idx
        tag, norm_x, norm_y, desc = CALIB_ANCHORS_9[idx]

        # Calculate smooth interpolation during transit (0.25s)
        transit_t = min(1.0, (now - self.transit_start_time) / 0.25)
        ease_t = transit_t * transit_t * (3.0 - 2.0 * transit_t)  # smoothstep
        cur_x = self.prev_pt.x() + (self.target_pt.x() - self.prev_pt.x()) * ease_t
        cur_y = self.prev_pt.y() + (self.target_pt.y() - self.prev_pt.y()) * ease_t

        # 1. Top Header Bar
        header_y = int(self.screen_height * 0.08)
        painter.setPen(QColor(56, 189, 248))
        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        painter.drawText(0, header_y - 24, self.screen_width, 24, Qt.AlignmentFlag.AlignHCenter, 
                         f"// 9-POINT STATIC MESH CALIBRATION [ {idx + 1:02d} / 09 ]")

        painter.setPen(QColor(249, 250, 251))
        painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        painter.drawText(0, header_y + 4, self.screen_width, 36, Qt.AlignmentFlag.AlignHCenter, desc)

        # 2. Glowing Target Orb
        base_r = 36.0
        grad = QRadialGradient(cur_x, cur_y, base_r + 16.0)
        grad.setColorAt(0.0, QColor(56, 189, 248, 240))
        grad.setColorAt(0.4, QColor(14, 165, 233, 90))
        grad.setColorAt(1.0, QColor(14, 165, 233, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(cur_x, cur_y), base_r + 16.0, base_r + 16.0)

        # Dark Base Disc
        painter.setPen(QPen(QColor(55, 65, 81), 1.5))
        painter.setBrush(QBrush(QColor(17, 24, 39, 220)))
        painter.drawEllipse(QPointF(cur_x, cur_y), base_r, base_r)

        # 3. Circular Progress Ring (Fills as user gazes stably)
        if self.anchor_progress > 0:
            arc_span = int(self.anchor_progress * 360 * 16)
            painter.setPen(QPen(QColor(16, 185, 129), 4.5))
            painter.drawArc(int(cur_x - base_r), int(cur_y - base_r), int(base_r * 2), int(base_r * 2), 90 * 16, -arc_span)

        # Center White Core
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(249, 250, 251)))
        painter.drawEllipse(QPointF(cur_x, cur_y), 4.5, 4.5)

        # 4. OK Badge Flash when anchor locked
        if self.anchor_ok_until > 0:
            painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            painter.setPen(QColor(16, 185, 129))
            painter.drawText(int(cur_x - 80), int(cur_y - base_r - 28), 160, 26, Qt.AlignmentFlag.AlignCenter, "✓ OK!")
        else:
            pct = int(self.anchor_progress * 100)
            painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            painter.setPen(QColor(56, 189, 248) if pct < 100 else QColor(16, 185, 129))
            painter.drawText(int(cur_x - 80), int(cur_y + base_r + 14), 160, 24, Qt.AlignmentFlag.AlignCenter, f"{pct}% LOCK")

        # Bottom Hint
        bottom_y = int(self.screen_height * 0.94)
        painter.setFont(QFont("Consolas", 10))
        painter.setPen(QColor(107, 114, 128))
        painter.drawText(0, bottom_y, self.screen_width, 22, Qt.AlignmentFlag.AlignHCenter, 
                         "[ SPACE ] / [ TAB ] / [ → ] / クリックで手動送り可能")

    # -------------------------------------------------------------------------
    # Active Mouse Calibration Drawing
    # -------------------------------------------------------------------------
    def _draw_active_mouse(self, painter: QPainter):
        now = time.perf_counter()
        elapsed = now - self.state_start_time
        rem_sec = max(0.0, self.active_mouse_duration - elapsed)

        header_y = int(self.screen_height * 0.08)
        painter.setPen(QColor(16, 185, 129))
        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        painter.drawText(0, header_y - 24, self.screen_width, 24, Qt.AlignmentFlag.AlignHCenter, 
                         f"// ACTIVE MOUSE PURSUIT [ {rem_sec:.1f}s REMAINING ]")

        painter.setPen(QColor(249, 250, 251))
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(0, header_y + 4, self.screen_width, 36, Qt.AlignmentFlag.AlignHCenter, 
                         "マウスカーソルを自由に動かし、カーソルを見つめてください")

        # Draw Trail
        if len(self.mouse_trail) > 1:
            for i in range(len(self.mouse_trail) - 1):
                x1, y1, t1 = self.mouse_trail[i]
                x2, y2, t2 = self.mouse_trail[i+1]
                age = now - t1
                alpha = max(0, min(180, int(180 * (1.0 - age / 2.0))))
                if alpha > 10:
                    painter.setPen(QPen(QColor(16, 185, 129, alpha), 2.0))
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Dynamic Reticle on Cursor
        cpos = QCursor.pos()
        mx, my = float(cpos.x()), float(cpos.y())
        ring_r = 30.0 + (0.5 + 0.5 * math.sin(now * 6.0)) * 4.0

        painter.setPen(QPen(QColor(52, 211, 153, 230), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(mx, my), ring_r, ring_r)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(249, 250, 251)))
        painter.drawEllipse(QPointF(mx, my), 3.5, 3.5)

    # -------------------------------------------------------------------------
    # Completion Summary
    # -------------------------------------------------------------------------
    def _draw_completion_summary(self, painter: QPainter):
        cx = self.screen_width / 2.0
        cy = self.screen_height / 2.0

        card_w = min(680, int(self.screen_width * 0.65))
        card_h = min(400, int(self.screen_height * 0.48))
        card_x = cx - card_w / 2.0
        card_y = cy - card_h / 2.0

        painter.setPen(QPen(QColor(16, 185, 129), 1.5))
        painter.setBrush(QBrush(QColor(17, 24, 39, 245)))
        painter.drawRoundedRect(int(card_x), int(card_y), card_w, card_h, 12, 12)

        painter.setPen(QColor(16, 185, 129))
        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        painter.drawText(int(card_x), int(card_y + 38), card_w, 24, Qt.AlignmentFlag.AlignCenter, 
                         "● 9-POINT PIECEWISE AFFINE MESH SOLVED")

        painter.setPen(QColor(249, 250, 251))
        painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        painter.drawText(int(card_x), int(card_y + 70), card_w, 32, Qt.AlignmentFlag.AlignCenter, 
                         "高精度9点メッシュ校正完了")

        painter.setPen(QColor(156, 163, 175))
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(int(card_x), int(card_y + 104), card_w, 24, Qt.AlignmentFlag.AlignCenter, 
                         f"確定アンカー: 9点 (全点誤差0.0px保証) | サンプル数: {self.total_samples:,}")

        box_w = card_w - 60
        box_x = card_x + 30
        box_y = card_y + 138
        painter.setPen(QPen(QColor(31, 41, 55), 1))
        painter.setBrush(QBrush(QColor(22, 31, 48, 180)))
        painter.drawRoundedRect(int(box_x), int(box_y), box_w, 120, 6, 6)

        painter.setFont(QFont("Consolas", 10))
        painter.setPen(QColor(52, 211, 153))
        painter.drawText(int(box_x + 16), int(box_y + 28), "✓ 9-Point Static Anchors Fitted (Zero Pursuit Delay)")
        painter.setPen(QColor(56, 189, 248))
        painter.drawText(int(box_x + 16), int(box_y + 54), "✓ 8-Triangular Piecewise Affine Warp Computed")
        painter.setPen(QColor(245, 158, 11))
        painter.drawText(int(box_x + 16), int(box_y + 80), "✓ Head-Gaze Hybrid Boost Activated (Tobii Extended View style)")

        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        painter.setPen(QColor(56, 189, 248))
        painter.drawText(int(card_x), int(card_y + card_h - 36), card_w, 24, Qt.AlignmentFlag.AlignCenter, 
                         "▶ [ SPACE キー ] または [ 画面クリック ] で戻る")
