import sys
import ctypes
import time
from typing import Tuple, Optional
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtWidgets import QWidget
from core.filter import GazePointFilter
from core.protocol import ARFaceFrame

# Win32 Constants for click-through & transparent overlay
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
GWL_EXSTYLE = -20

class HUDOverlay(QWidget):
    """
    Hallmark 'Tally' Precision HUD Overlay.
    Ultra-lightweight borderless, click-through, always-on-top transparent overlay for gaze tracking.
    """
    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        super().__init__()
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Styling Tokens
        self.pointer_radius = 24.0
        self.pointer_color = QColor(0, 240, 255, 220)  # Default Cyan
        self.pointer_fill_color = QColor(0, 240, 255, 45)
        self.show_crosshair = True
        self.hud_visible = True

        # Target filtered positions from UDP stream
        self.target_x = screen_width / 2.0
        self.target_y = screen_height / 2.0
        self.current_x = self.target_x
        self.current_y = self.target_y
        self.is_blinking = False
        self.last_update_time = time.perf_counter()

        # 1€ Filter (Ultra-Smooth default)
        self.filter = GazePointFilter(min_cutoff=0.4, beta=0.008)

        self._init_window()
        self._enable_click_through()

        # Render loop: ~144Hz (7ms)
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._on_render_tick)
        self.render_timer.start(7)

    def _init_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setGeometry(0, 0, self.screen_width, self.screen_height)

    def _enable_click_through(self):
        if sys.platform == "win32":
            try:
                hwnd = int(self.winId())
                user32 = ctypes.windll.user32
                ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                new_style = ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            except Exception as e:
                print(f"[HUDOverlay] Win32 style error: {e}")

    def update_gaze(self, raw_x: float, raw_y: float, frame: Optional[ARFaceFrame] = None):
        now = time.perf_counter()
        fx, fy = self.filter.filter(raw_x, raw_y, now)
        self.target_x = fx
        self.target_y = fy

        if frame:
            self.is_blinking = (frame.blink_left > 0.6 and frame.blink_right > 0.6)

        self.last_update_time = now

    def set_smoothing(self, min_cutoff: float, beta: float):
        self.filter.update_params(min_cutoff, beta)

    def set_pointer_style(self, radius: float, color: QColor, fill_alpha: int = 45):
        self.pointer_radius = radius
        self.pointer_color = color
        self.pointer_fill_color = QColor(color.red(), color.green(), color.blue(), fill_alpha)

    def _on_render_tick(self):
        if not self.hud_visible:
            return

        # High-frequency sub-frame exponential interpolation (Butter-Smooth Glide)
        lerp_rate = 0.35
        self.current_x += (self.target_x - self.current_x) * lerp_rate
        self.current_y += (self.target_y - self.current_y) * lerp_rate

        self.update()

    def paintEvent(self, event):
        if not self.hud_visible or self.is_blinking:
            return

        # Smooth fadeout on stale data
        elapsed = time.perf_counter() - self.last_update_time
        if elapsed > 0.5:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.current_x
        cy = self.current_y
        r = self.pointer_radius

        # 1. Outer Reticle Ring
        pen = QPen(self.pointer_color, 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(self.pointer_fill_color))
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # 2. Precision Center Pin
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.pointer_color))
        painter.drawEllipse(QPointF(cx, cy), 2.5, 2.5)

        # 3. Precision Optical Crosshair Ticks
        if self.show_crosshair:
            tick_len = r * 0.35
            painter.setPen(QPen(self.pointer_color, 1.2))
            # North
            painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy - r + tick_len))
            # South
            painter.drawLine(QPointF(cx, cy + r), QPointF(cx, cy + r - tick_len))
            # West
            painter.drawLine(QPointF(cx - r, cy), QPointF(cx - r + tick_len, cy))
            # East
            painter.drawLine(QPointF(cx + r, cy), QPointF(cx + r - tick_len, cy))
