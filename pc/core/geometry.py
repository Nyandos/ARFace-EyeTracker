import numpy as np
from typing import Tuple, Optional
from .protocol import ARFaceFrame

def quaternion_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    """
    Convert quaternion [x, y, z, w] to 3x3 rotation matrix.
    """
    x, y, z, w = q
    # Normalize quaternion to avoid distortion
    norm = math_norm = np.linalg.norm(q)
    if math_norm > 1e-6:
        x, y, z, w = x / norm, y / norm, z / norm, w / norm
    else:
        x, y, z, w = 0.0, 0.0, 0.0, 1.0

    return np.array([
        [1 - 2*(y**2 + z**2), 2*(x*y - z*w),     2*(x*z + y*w)],
        [2*(x*y + z*w),     1 - 2*(x**2 + z**2), 2*(y*z - x*w)],
        [2*(x*z - y*w),     2*(y*z + x*w),     1 - 2*(x**2 + y**2)]
    ], dtype=np.float32)


class GeometryEstimator:
    """
    3D Spatial Raycasting & Gaze Projection Engine.
    Fuses Head Pose Rotation Matrix and Eye Gaze Vectors to achieve head-rotation invariance.
    """
    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.gaze_gain = 1.6

    def set_gaze_gain(self, gain: float):
        self.gaze_gain = max(0.5, min(5.0, float(gain)))

    def compute_world_gaze_ray(self, frame: ARFaceFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes the true 3D Gaze Ray in Camera/World space:
        Ray Origin: Eye center in world space
        Ray Direction: R_head * v_eye (Compensates for head rotations!)
        """
        R_head = quaternion_to_rotation_matrix(frame.head_rot)
        v_eye_local = frame.left_gaze  # Local gaze direction vector

        # Rotate local eye vector into world space by head rotation
        v_world = R_head @ v_eye_local
        # Normalize
        v_world_norm = np.linalg.norm(v_world)
        if v_world_norm > 1e-6:
            v_world = v_world / v_world_norm
        else:
            v_world = np.array([0.0, 0.0, -1.0], dtype=np.float32)

        # Eye origin in meters (Head position + slight eye offset in head frame)
        eye_offset_local = np.array([0.0, 0.03, 0.04], dtype=np.float32)
        eye_pos_world = frame.head_pos + (R_head @ eye_offset_local)

        return eye_pos_world, v_world

    def extract_features(self, frame: ARFaceFrame) -> np.ndarray:
        """
        Extract features for calibration, based on the world-space gaze ray and head state.
        """
        eye_origin, v_world = self.compute_world_gaze_ray(frame)
        R_head = quaternion_to_rotation_matrix(frame.head_rot)
        pitch = np.arcsin(np.clip(-R_head[1, 2], -1.0, 1.0))
        roll = np.arctan2(R_head[0, 2], R_head[2, 2])
        yaw = np.arctan2(R_head[1, 0], R_head[1, 1])

        # Direction tangents (Gaze angle in world space)
        # z is negative towards screen/front
        z_denom = abs(v_world[2]) if abs(v_world[2]) > 1e-3 else 1.0
        gaze_tan_x = v_world[0] / z_denom
        gaze_tan_y = v_world[1] / z_denom

        features = [
            gaze_tan_x * 3.0,   # Primary world gaze X
            gaze_tan_y * 3.0,   # Primary world gaze Y
            v_world[0], v_world[1], v_world[2],
            eye_origin[0], eye_origin[1], eye_origin[2],
            yaw, pitch, roll
        ]
        return np.array(features, dtype=np.float32)

    def estimate_raw_screen_pos(self, frame: ARFaceFrame) -> Tuple[float, float]:
        """
        Estimate 2D screen coordinates using 3D world gaze raycasting.
        Invariant to head rotation.
        """
        eye_origin, v_world = self.compute_world_gaze_ray(frame)

        # Gaze slope in world coordinate
        z_denom = abs(v_world[2]) if abs(v_world[2]) > 0.1 else 0.1
        slope_x = v_world[0] / z_denom
        slope_y = v_world[1] / z_denom

        # Angular span mapping to normalized screen coordinates
        # Typical eye span: slope_x ~ ±0.35 covers 16:9 monitor
        norm_x = 0.5 + (slope_x / 0.28) * self.gaze_gain
        norm_y = 0.5 - (slope_y / 0.20) * self.gaze_gain

        # Head position subtle parallax correction (eye translation relative to screen center)
        # If head moves right by 10cm, screen center moves left relative to eye
        norm_x += (eye_origin[0] / 0.40) * 0.10
        norm_y -= (eye_origin[1] / 0.30) * 0.10

        px = norm_x * self.screen_width
        py = norm_y * self.screen_height

        margin = 150.0
        px = float(np.clip(px, -margin, self.screen_width + margin))
        py = float(np.clip(py, -margin, self.screen_height + margin))

        return px, py
