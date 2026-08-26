import math
import numpy as np
from typing import Tuple, Optional
from .protocol import ARFaceFrame

def quaternion_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    """
    Convert quaternion [x, y, z, w] to 3x3 rotation matrix.
    """
    x, y, z, w = q
    norm = np.linalg.norm(q)
    if norm > 1e-6:
        x, y, z, w = x / norm, y / norm, z / norm, w / norm
    else:
        x, y, z, w = 0.0, 0.0, 0.0, 1.0

    return np.array([
        [1 - 2*(y**2 + z**2), 2*(x*y - z*w),     2*(x*z + y*w)],
        [2*(x*y + z*w),     1 - 2*(x**2 + z**2), 2*(y*z - x*w)],
        [2*(x*z - y*w),     2*(y*z + x*w),     1 - 2*(x**2 + y**2)]
    ], dtype=np.float32)

def quaternion_to_euler_angles(q: np.ndarray) -> Tuple[float, float, float]:
    """
    Directly and robustly converts quaternion [x, y, z, w] to (yaw, pitch, roll) in radians.
    - Yaw: Rotation around Y axis (Left/Right)
    - Pitch: Rotation around X axis (Up/Down)
    - Roll: Rotation around Z axis (Tilt)
    """
    x, y, z, w = q
    norm = math.sqrt(x*x + y*y + z*z + w*w)
    if norm > 1e-6:
        x, y, z, w = x/norm, y/norm, z/norm, w/norm
    else:
        return 0.0, 0.0, 0.0

    # Yaw (Y-axis rotation, turn head left/right)
    siny_cosp = 2.0 * (w * y - z * x)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = float(math.atan2(siny_cosp, cosy_cosp))

    # Pitch (X-axis rotation, nod head up/down)
    sinp = 2.0 * (w * x + y * z)
    if abs(sinp) >= 1.0:
        pitch = float(math.copysign(math.pi / 2.0, sinp))
    else:
        pitch = float(math.asin(sinp))

    # Roll (Z-axis rotation, tilt head)
    sinr_cosp = 2.0 * (w * z - x * y)
    cosr_cosp = 1.0 - 2.0 * (x * x + z * z)
    roll = float(math.atan2(sinr_cosp, cosr_cosp))

    return yaw, pitch, roll

def euler_angles_from_matrix(R: np.ndarray) -> Tuple[float, float, float]:
    """Backward-compatible helper: extract (yaw, pitch, roll) from 3x3 rotation matrix"""
    pitch = float(math.asin(np.clip(-R[1, 2], -1.0, 1.0)))
    yaw = float(math.atan2(R[0, 2], R[2, 2]))
    roll = float(math.atan2(R[1, 0], R[1, 1]))
    return yaw, pitch, roll

def matrix_from_euler(yaw: float, pitch: float, roll: float) -> np.ndarray:
    """Construct rotation matrix from scaled (yaw, pitch, roll)"""
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)

    # R = Ry(yaw) * Rx(pitch) * Rz(roll)
    R = np.array([
        [cy*cr + sy*sp*sr, -cy*sr + sy*sp*cr, sy*cp],
        [cp*sr,            cp*cr,            -sp],
        [-sy*cr + cy*sp*sr, sy*sr + cy*sp*cr, cy*cp]
    ], dtype=np.float32)
    return R


class GeometryEstimator:
    """
    3D Spatial Raycasting & Binocular Gaze Fusion Engine.
    Combines:
    1. Binocular Gaze Fusion (average left & right eye gaze vectors) to eliminate single-eye occlusion.
    2. TrueDepth 3D lookAtPoint vector blend for wide-angle stability.
    3. Calibrated Head Decoupling Gains (Yaw & Pitch) to cancel drift when turning/tilting head.
    """
    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.gaze_gain = 1.6

        # Head Pose Decoupling Gains (Calibrated via Phase 2)
        self.head_gain_yaw = 1.0
        self.head_gain_pitch = 1.0

    def set_gaze_gain(self, gain: float):
        self.gaze_gain = max(0.5, min(5.0, float(gain)))

    def set_head_decoupling_gains(self, gain_yaw: float, gain_pitch: float):
        self.head_gain_yaw = float(np.clip(gain_yaw, 0.4, 1.8))
        self.head_gain_pitch = float(np.clip(gain_pitch, 0.4, 1.8))
        print(f"[Geometry] Updated Head Decoupling Gains: Yaw={self.head_gain_yaw:.2f}, Pitch={self.head_gain_pitch:.2f}")

    def compute_world_gaze_ray(self, frame: ARFaceFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes the unified 3D World Gaze Ray fusing left eye, right eye, and lookAtPoint,
        with calibrated Yaw/Pitch head-motion decoupling.
        """
        yaw, pitch, roll = quaternion_to_euler_angles(frame.head_rot)

        # Apply calibrated decoupling gains to head rotation
        R_head = matrix_from_euler(yaw * self.head_gain_yaw, pitch * self.head_gain_pitch, roll)

        # 1. Binocular Gaze Fusion
        norm_l = np.linalg.norm(frame.left_gaze)
        norm_r = np.linalg.norm(frame.right_gaze)
        
        if norm_l > 1e-3 and norm_r > 1e-3:
            v_eye_local = 0.5 * (frame.left_gaze / norm_l + frame.right_gaze / norm_r)
        elif norm_l > 1e-3:
            v_eye_local = frame.left_gaze / norm_l
        elif norm_r > 1e-3:
            v_eye_local = frame.right_gaze / norm_r
        else:
            v_eye_local = np.array([0.0, 0.0, -1.0], dtype=np.float32)

        v_eye_norm = np.linalg.norm(v_eye_local)
        if v_eye_norm > 1e-6:
            v_eye_local /= v_eye_norm

        # 2. Blend with lookAtPoint if valid
        norm_look = np.linalg.norm(frame.look_at_point)
        if norm_look > 0.01:
            v_look_dir = frame.look_at_point / norm_look
            v_fused_local = 0.75 * v_eye_local + 0.25 * v_look_dir
            norm_fused = np.linalg.norm(v_fused_local)
            if norm_fused > 1e-6:
                v_eye_local = v_fused_local / norm_fused

        # 3. Rotate local eye vector into world space by head rotation
        v_world = R_head @ v_eye_local
        v_world_norm = np.linalg.norm(v_world)
        if v_world_norm > 1e-6:
            v_world = v_world / v_world_norm
        else:
            v_world = np.array([0.0, 0.0, -1.0], dtype=np.float32)

        # Eye origin in meters (Head position + eye offset in head frame)
        eye_offset_local = np.array([0.0, 0.03, 0.04], dtype=np.float32)
        eye_pos_world = frame.head_pos + (R_head @ eye_offset_local)

        return eye_pos_world, v_world

    def extract_features(self, frame: ARFaceFrame) -> np.ndarray:
        """
        Extract multi-dimensional geometric features for calibration.
        """
        eye_origin, v_world = self.compute_world_gaze_ray(frame)
        yaw, pitch, roll = quaternion_to_euler_angles(frame.head_rot)

        z_denom = abs(v_world[2]) if abs(v_world[2]) > 1e-3 else 1.0
        gaze_tan_x = v_world[0] / z_denom
        gaze_tan_y = v_world[1] / z_denom

        features = [
            gaze_tan_x * 3.0,
            gaze_tan_y * 3.0,
            v_world[0], v_world[1], v_world[2],
            eye_origin[0], eye_origin[1], eye_origin[2],
            yaw, pitch, roll,
            frame.look_at_point[0], frame.look_at_point[1]
        ]
        return np.array(features, dtype=np.float32)

    def estimate_raw_screen_pos(self, frame: ARFaceFrame) -> Tuple[float, float]:
        """
        Estimate 2D screen coordinates using 3D world gaze raycasting.
        """
        eye_origin, v_world = self.compute_world_gaze_ray(frame)

        z_denom = abs(v_world[2]) if abs(v_world[2]) > 0.1 else 0.1
        slope_x = v_world[0] / z_denom
        slope_y = v_world[1] / z_denom

        norm_x = 0.5 + (slope_x / 0.28) * self.gaze_gain
        norm_y = 0.5 - (slope_y / 0.20) * self.gaze_gain

        norm_x += (eye_origin[0] / 0.40) * 0.10
        norm_y -= (eye_origin[1] / 0.30) * 0.10

        px = norm_x * self.screen_width
        py = norm_y * self.screen_height

        margin = 150.0
        px = float(np.clip(px, -margin, self.screen_width + margin))
        py = float(np.clip(py, -margin, self.screen_height + margin))

        return px, py
