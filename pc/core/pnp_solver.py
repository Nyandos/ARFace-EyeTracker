import math
import numpy as np
import cv2
from typing import Tuple, Optional, Dict
from dataclasses import dataclass

@dataclass
class MonitorSpatialPose:
    """Estimated 3D Pose of PC Monitor relative to iPhone TrueDepth Sensor"""
    pos_x_m: float           # Lateral offset (positive: right of monitor center)
    pos_y_m: float           # Vertical offset (negative: below monitor bottom)
    pos_z_m: float           # Depth offset (positive: in front of monitor plane)
    pitch_deg: float         # Upward tilt angle of iPhone (degrees)
    roll_deg: float          # Side tilt angle of iPhone (degrees)
    yaw_deg: float           # Horizontal heading angle of iPhone (degrees)
    monitor_width_m: float   # Width of active display in meters
    monitor_height_m: float  # Height of active display in meters
    R_sensor_to_mon: np.ndarray # 3x3 Rotation matrix
    t_sensor_to_mon: np.ndarray # 3x1 Translation vector (meters)

    def describe(self) -> str:
        h_cm = self.pos_y_m * 100.0
        d_cm = self.pos_z_m * 100.0
        x_cm = self.pos_x_m * 100.0
        return (f"モニター下端から: 下 {abs(h_cm):.1f}cm | 手前 {d_cm:.1f}cm | "
                f"左右 {x_cm:+.1f}cm | 仰角 {self.pitch_deg:.1f}°")


def solve_monitor_pnp(
    corners_2d: np.ndarray,
    monitor_w_m: float,
    monitor_h_m: float,
    img_w: int,
    img_h: int,
    fov_deg: float = 65.0,
    imu_pitch_deg: Optional[float] = None
) -> Optional[MonitorSpatialPose]:
    """
    Solve Perspective-n-Point (PnP) geometry given 4 clicked corner points on the monitor photo.
    corners_2d: (4, 2) array ordered: [Top-Left, Top-Right, Bottom-Right, Bottom-Left]
    """
    if len(corners_2d) != 4:
        return None

    # 1. 3D Object Coordinates of Monitor Corners (Origin at Monitor Center, Z=0)
    # Standard OpenCV Camera space: X is right, Y is down, Z is forward
    hw = monitor_w_m * 0.5
    hh = monitor_h_m * 0.5
    obj_pts = np.array([
        [-hw, -hh, 0.0],   # Top-Left (Y is negative / up in scene)
        [ hw, -hh, 0.0],   # Top-Right
        [ hw,  hh, 0.0],   # Bottom-Right (Y is positive / down in scene)
        [-hw,  hh, 0.0],   # Bottom-Left
    ], dtype=np.float32)

    img_pts = np.array(corners_2d, dtype=np.float32)

    # 2. Camera Intrinsic Matrix K (Pinhole model based on known iPhone FOV)
    focal_length = (img_w * 0.5) / math.tan(math.radians(fov_deg * 0.5))
    cx = img_w * 0.5
    cy = img_h * 0.5

    K = np.array([
        [focal_length, 0.0,          cx],
        [0.0,          focal_length, cy],
        [0.0,          0.0,          1.0]
    ], dtype=np.float32)

    dist_coeffs = np.zeros(4, dtype=np.float32)

    # 3. Solve PnP using IPPE Square solver
    success, rvec, tvec = cv2.solvePnP(
        obj_pts, img_pts, K, dist_coeffs, flags=cv2.SOLVEPNP_IPPE_SQUARE
    )

    if not success:
        success, rvec, tvec = cv2.solvePnP(
            obj_pts, img_pts, K, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
        )
        if not success:
            return None

    R_cam, _ = cv2.Rodrigues(rvec)
    t_cam = tvec.flatten()

    # Offset to TrueDepth front sensor (iPhone thickness ~7.8mm)
    phone_thickness = 0.008  # 8mm
    pos_x = float(t_cam[0])
    pos_y = -float(t_cam[1] - hh)  # Relative to monitor bottom edge (negative = below monitor)
    pos_z = float(t_cam[2]) + phone_thickness

    # Extract Physical Upward Tilt (Pitch relative to vertical monitor plane)
    raw_pitch = float(math.degrees(math.atan2(R_cam[1, 2], R_cam[2, 2])))
    pitch = 180.0 - abs(raw_pitch)
    pitch = float(np.clip(pitch, 5.0, 75.0))

    roll = float(math.degrees(math.atan2(R_cam[0, 1], R_cam[0, 0])))
    yaw = float(math.degrees(math.atan2(R_cam[0, 2], math.sqrt(R_cam[1, 2]**2 + R_cam[2, 2]**2))))

    # Fuse with IMU Pitch if available
    if imu_pitch_deg is not None:
        pitch = 0.7 * pitch + 0.3 * imu_pitch_deg

    return MonitorSpatialPose(
        pos_x_m=pos_x,
        pos_y_m=pos_y,
        pos_z_m=pos_z,
        pitch_deg=pitch,
        roll_deg=roll,
        yaw_deg=yaw,
        monitor_width_m=monitor_w_m,
        monitor_height_m=monitor_h_m,
        R_sensor_to_mon=R_cam,
        t_sensor_to_mon=tvec
    )
