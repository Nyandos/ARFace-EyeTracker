import math
import numpy as np
from typing import Optional, Tuple, List
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import QWidget
from core.protocol import ARFaceFrame

class FacePreviewWidget(QWidget):
    """
    Hallmark 'Tally' Precision 3D Face & Gaze Wireframe Inspector.
    Renders an instrument-grade, real-time 3D vector wireframe of the tracked head,
    interactive gaze rays, dynamic blink eyelids, and aircraft-style attitude pitch/roll ladders.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 220)
        self.setStyleSheet("background-color: #0b0f17; border-radius: 8px; border: 1px solid #1f2937;")

        self.current_frame: Optional[ARFaceFrame] = None
        self.is_tracking = False

        # Euler angles (deg)
        self.pitch_deg = 0.0
        self.yaw_deg = 0.0
        self.roll_deg = 0.0

        # Colors (Tally Slate & Cyber Neon Palette)
        self.col_wire = QColor(56, 189, 248, 220)       # Cyan Head Wireframe
        self.col_wire_dim = QColor(56, 189, 248, 50)
        self.col_grid = QColor(31, 41, 55, 180)          # Subtle Background Grid
        self.col_axis = QColor(75, 85, 99, 150)          # Center Horizon Line
        self.col_gaze = QColor(52, 211, 153, 240)        # Emerald Gaze Rays
        self.col_pupil = QColor(249, 250, 251, 240)      # White Eye Pupils
        self.col_text = QColor(156, 163, 175)

        # 3D Head Base Geometry Model (Local coordinate frame in meters, +Z forward, +Y up, +X right)
        self._init_head_model()

    def _init_head_model(self):
        # Key landmark vertices for minimalist face mesh
        # [x, y, z] in local face coordinates
        self.nodes = {
            "forehead_top": np.array([0.0, 0.10, 0.02]),
            "forehead_l": np.array([-0.065, 0.08, 0.04]),
            "forehead_r": np.array([0.065, 0.08, 0.04]),
            
            "temple_l": np.array([-0.085, 0.04, -0.02]),
            "temple_r": np.array([0.085, 0.04, -0.02]),

            "cheek_l": np.array([-0.075, -0.03, 0.03]),
            "cheek_r": np.array([0.075, -0.03, 0.03]),

            "jaw_l": np.array([-0.055, -0.09, 0.01]),
            "jaw_r": np.array([0.055, -0.09, 0.01]),
            "chin": np.array([0.0, -0.11, 0.04]),

            # Nose structure
            "nose_bridge": np.array([0.0, 0.02, 0.065]),
            "nose_tip": np.array([0.0, -0.015, 0.095]),
            "nose_l": np.array([-0.02, -0.025, 0.07]),
            "nose_r": np.array([0.02, -0.025, 0.07]),

            # Eyes (center anchor)
            "eye_l_center": np.array([-0.033, 0.03, 0.055]),
            "eye_r_center": np.array([0.033, 0.03, 0.055]),

            # Mouth line
            "mouth_l": np.array([-0.03, -0.06, 0.055]),
            "mouth_r": np.array([0.03, -0.06, 0.055]),
            "mouth_mid": np.array([0.0, -0.062, 0.062]),
        }

        # Wireframe edges (connect node pairs)
        self.edges = [
            # Contour
            ("forehead_top", "forehead_l"), ("forehead_l", "temple_l"), ("temple_l", "cheek_l"),
            ("cheek_l", "jaw_l"), ("jaw_l", "chin"), ("chin", "jaw_r"), ("jaw_r", "cheek_r"),
            ("cheek_r", "temple_r"), ("temple_r", "forehead_r"), ("forehead_r", "forehead_top"),

            # Forehead bridge
            ("forehead_l", "forehead_r"),
            ("forehead_top", "nose_bridge"),

            # Nose
            ("nose_bridge", "nose_tip"),
            ("nose_tip", "nose_l"), ("nose_tip", "nose_r"),
            ("nose_l", "nose_bridge"), ("nose_r", "nose_bridge"),

            # Cheeks to nose
            ("cheek_l", "nose_l"), ("cheek_r", "nose_r"),

            # Mouth
            ("mouth_l", "mouth_mid"), ("mouth_mid", "mouth_r"),
            ("chin", "mouth_mid")
        ]

    def update_frame(self, frame: Optional[ARFaceFrame]):
        self.current_frame = frame
        self.is_tracking = (frame is not None)
        if frame:
            # Extract Euler angles from quaternion [qx, qy, qz, qw]
            qx, qy, qz, qw = frame.head_rot
            # Roll (Z), Pitch (X), Yaw (Y)
            sinr_cosp = 2 * (qw * qx + qy * qz)
            cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
            roll = math.atan2(sinr_cosp, cosr_cosp)

            sinp = 2 * (qw * qy - qz * qx)
            sinp = max(-1.0, min(1.0, sinp))
            pitch = math.asin(sinp)

            siny_cosp = 2 * (qw * qz + qx * qy)
            cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
            yaw = math.atan2(siny_cosp, cosy_cosp)

            self.pitch_deg = math.degrees(pitch)
            self.yaw_deg = math.degrees(yaw)
            self.roll_deg = math.degrees(roll)
        self.update()

    def _quat_to_rot_matrix(self, q: np.ndarray) -> np.ndarray:
        """Converts quaternion [qx, qy, qz, qw] to 3x3 rotation matrix"""
        qx, qy, qz, qw = q
        return np.array([
            [1 - 2*(qy*qy + qz*qz), 2*(qx*qy - qz*qw),     2*(qx*qz + qy*qw)],
            [2*(qx*qy + qz*qw),     1 - 2*(qx*qx + qz*qz), 2*(qy*qz - qx*qw)],
            [2*(qx*qz - qy*qw),     2*(qy*qz + qx*qw),     1 - 2*(qx*qx + qy*qy)]
        ], dtype=np.float32)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        # 1. Dark Technical Background & Crosshair Grid
        painter.fillRect(0, 0, w, h, QColor(11, 15, 23))

        painter.setPen(QPen(self.col_grid, 1, Qt.PenStyle.DashLine))
        painter.drawLine(0, int(cy), w, int(cy))
        painter.drawLine(int(cx), 0, int(cx), h)

        # Concentric Radar rings
        painter.drawEllipse(QPointF(cx, cy), 45, 45)
        painter.drawEllipse(QPointF(cx, cy), 90, 90)

        # Telemetry Header badge
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        if self.is_tracking and self.current_frame:
            painter.setPen(QColor(52, 211, 153))
            painter.drawText(12, 18, "● 3D HEAD & GAZE // ONLINE")
        else:
            painter.setPen(QColor(107, 114, 128))
            painter.drawText(12, 18, "○ 3D HEAD & GAZE // NO SIGNAL")
            painter.setFont(QFont("Segoe UI", 11))
            painter.setPen(QColor(75, 85, 99))
            painter.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, "Awaiting UDP Face Stream...")
            return

        frame = self.current_frame
        rot_mat = self._quat_to_rot_matrix(frame.head_rot)

        # Camera projection parameters
        fov_scale = min(w, h) * 1.15
        cam_dist = 0.55  # virtual camera depth

        def project_3d(pt_local: np.ndarray) -> QPointF:
            # Rotate local point by head rotation
            # Local Z points forward from face, Y up, X right
            pt_rot = rot_mat @ pt_local
            # Perspective divide
            z_cam = pt_rot[2] + cam_dist
            if z_cam < 0.05:
                z_cam = 0.05
            px = cx + (pt_rot[0] * fov_scale) / z_cam
            py = cy - (pt_rot[1] * fov_scale) / z_cam
            return QPointF(px, py)

        # Project all wireframe vertices
        proj_nodes = {}
        for name, pt in self.nodes.items():
            proj_nodes[name] = project_3d(pt)

        # 2. Draw Wireframe Facemesh
        painter.setPen(QPen(self.col_wire, 1.4))
        for edge in self.edges:
            p1 = proj_nodes.get(edge[0])
            p2 = proj_nodes.get(edge[1])
            if p1 and p2:
                painter.drawLine(p1, p2)

        # 3. Dynamic Eyelids (Blink representation)
        blink_l = max(0.0, min(1.0, frame.blink_left))
        blink_r = max(0.0, min(1.0, frame.blink_right))

        eye_w = 11.0
        eye_h_l = max(1.5, 7.0 * (1.0 - blink_l * 0.9))
        eye_h_r = max(1.5, 7.0 * (1.0 - blink_r * 0.9))

        p_eye_l = proj_nodes["eye_l_center"]
        p_eye_r = proj_nodes["eye_r_center"]

        # Draw Eye Outlines
        painter.setPen(QPen(QColor(56, 189, 248), 1.3))
        painter.setBrush(QBrush(QColor(17, 24, 39, 180)))
        painter.drawEllipse(p_eye_l, eye_w / 2.0, eye_h_l / 2.0)
        painter.drawEllipse(p_eye_r, eye_w / 2.0, eye_h_r / 2.0)

        # Pupils
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.col_pupil))
        if blink_l < 0.8:
            painter.drawEllipse(p_eye_l, 2.0, 2.0)
        if blink_r < 0.8:
            painter.drawEllipse(p_eye_r, 2.0, 2.0)

        # 4. Gaze Direction Rays (Emerald Lasers)
        # Transform eye gaze vectors into world space
        ray_len = 0.18  # 18cm gaze vector in 3D
        l_gaze_local = frame.left_gaze * ray_len
        r_gaze_local = frame.right_gaze * ray_len

        p_gaze_l_end = project_3d(self.nodes["eye_l_center"] + l_gaze_local)
        p_gaze_r_end = project_3d(self.nodes["eye_r_center"] + r_gaze_local)

        # Draw Gaze Rays
        gaze_pen = QPen(self.col_gaze, 1.8)
        painter.setPen(gaze_pen)
        painter.drawLine(p_eye_l, p_gaze_l_end)
        painter.drawLine(p_eye_r, p_gaze_r_end)

        # Gaze End Reticles
        painter.setBrush(QBrush(self.col_gaze))
        painter.drawEllipse(p_gaze_l_end, 2.5, 2.5)
        painter.drawEllipse(p_gaze_r_end, 2.5, 2.5)

        # 5. Bottom Telemetry Overlay (Attitude + Blinks)
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Medium))
        painter.setPen(self.col_text)
        
        y_bottom = h - 10
        attitude_str = f"PITCH: {self.pitch_deg:+.1f}°  YAW: {self.yaw_deg:+.1f}°  ROLL: {self.roll_deg:+.1f}°"
        blink_str = f"BLINK L:{blink_l:.2f} R:{blink_r:.2f}"
        
        painter.drawText(12, y_bottom - 14, attitude_str)
        painter.drawText(12, y_bottom, blink_str)
