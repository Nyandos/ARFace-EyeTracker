import json
import os
import math
import numpy as np
from typing import List, Tuple, Optional, Dict
from .protocol import ARFaceFrame
from .geometry import GeometryEstimator, quaternion_to_euler_angles, quaternion_to_rotation_matrix

# 9 Precision Anchor Points (Normalized Screen Coordinates [0, 1])
# Index 0: Center, then clockwise perimeter starting from Top
CALIB_ANCHORS_9 = [
    ("CENTER", 0.50, 0.50, "中央の白ドットを注視 (ゼロ点ロック)"),
    ("TOP",    0.50, 0.05, "上辺中央を注視"),
    ("TOP_R",  0.95, 0.05, "右上隅を注視"),
    ("RIGHT",  0.95, 0.50, "右辺中央を注視"),
    ("BOT_R",  0.95, 0.95, "右下隅を注視"),
    ("BOTTOM", 0.50, 0.95, "下辺中央を注視"),
    ("BOT_L",  0.05, 0.95, "左下隅を注視"),
    ("LEFT",   0.05, 0.50, "左辺中央を注視"),
    ("TOP_L",  0.05, 0.05, "左上隅を注視"),
]

# 8 Triangular Segments connecting Center (0) to adjacent perimeter anchors (1..8)
TRIANGLE_INDICES = [
    (0, 1, 2),  # Center - Top - Top_R
    (0, 2, 3),  # Center - Top_R - Right
    (0, 3, 4),  # Center - Right - Bot_R
    (0, 4, 5),  # Center - Bot_R - Bottom
    (0, 5, 6),  # Center - Bottom - Bot_L
    (0, 6, 7),  # Center - Bot_L - Left
    (0, 7, 8),  # Center - Left - Top_L
    (0, 8, 1),  # Center - Top_L - Top
]


def solve_affine_2d(src_pts: np.ndarray, dst_pts: np.ndarray) -> np.ndarray:
    """
    Solves 2x3 affine transformation matrix M such that dst = M @ [src; 1].
    Exact solution for 3 non-collinear point pairs.
    """
    # src_pts: (3, 2), dst_pts: (3, 2)
    A = np.column_stack([src_pts, np.ones(3, dtype=np.float32)])  # (3, 3)
    # A * M.T = dst_pts => M.T = inv(A) * dst_pts => M = (inv(A) * dst_pts).T
    try:
        M_T = np.linalg.solve(A, dst_pts)  # (3, 2)
        return M_T.T  # (2, 3)
    except np.linalg.LinAlgError:
        # Fallback pseudo-inverse if nearly singular
        return (np.linalg.pinv(A) @ dst_pts).T


def point_in_triangle_2d(pt: np.ndarray, v0: np.ndarray, v1: np.ndarray, v2: np.ndarray) -> bool:
    """Check if 2D point lies inside triangle using barycentric cross products"""
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = sign(pt, v0, v1)
    d2 = sign(pt, v1, v2)
    d3 = sign(pt, v2, v0)

    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


class Calibrator:
    """
    Industrial-Grade 9-Point Piecewise Affine Mesh Calibrator with Head-Gaze Hybrid Boost.
    Architecture:
    - 9 Static Anchor Points (Center + 8 Perimeter): Eliminates human pursuit delay & saccade noise.
    - 8-Triangular Piecewise Affine Warp: Mathematical guarantee of EXACT 0-error at all anchor points.
    - Head-Gaze Hybrid Boost (Tobii Extended View style): Boosts peripheral gaze via head yaw/pitch,
      letting users effortlessly snap into extreme corners and screen edges.
    """
    def __init__(self, geometry: GeometryEstimator, save_path: str = "calibration_data.json"):
        self.geometry = geometry
        self.save_path = save_path
        self.is_calibrated = False

        # Anchor Sample Storage (9 Points)
        self.anchor_samples: Dict[int, List[np.ndarray]] = {i: [] for i in range(len(CALIB_ANCHORS_9))}

        # Solved Calibration Model
        self.anchor_gaze_centers: Optional[np.ndarray] = None  # (9, 2) median gaze vectors
        self.anchor_screen_pts: Optional[np.ndarray] = None    # (9, 2) screen pixel coordinates
        self.triangle_affines: Optional[List[np.ndarray]] = None # 8x (2, 3) Affine matrices

        # Baseline Head Pose locked at Center Anchor (Index 0)
        self.base_yaw: float = 0.0
        self.base_pitch: float = 0.0

        # Head-Gaze Hybrid Boost Parameters
        self.hybrid_boost_enabled: bool = True
        self.hybrid_boost_gain: float = 1.0  # Adjustable from 0.0 (off) to 2.5 (strong)

        self.load()

    def reset_dynamic_samples(self):
        """Reset all anchor sample buffers"""
        self.anchor_samples = {i: [] for i in range(len(CALIB_ANCHORS_9))}

    def add_anchor_sample(self, anchor_idx: int, frame: ARFaceFrame):
        """Record calibration sample for a specific static anchor point"""
        if anchor_idx not in self.anchor_samples:
            return

        eye_origin, v_world = self.geometry.compute_world_gaze_ray(frame)
        z_denom = abs(v_world[2]) if abs(v_world[2]) > 1e-3 else 1.0
        gx = float(v_world[0] / z_denom)
        gy = float(v_world[1] / z_denom)

        yaw, pitch, roll = quaternion_to_euler_angles(frame.head_rot)
        sample = np.array([gx, gy, yaw, pitch], dtype=np.float32)
        self.anchor_samples[anchor_idx].append(sample)

    def fit(self, screen_w: int = 1920, screen_h: int = 1080) -> bool:
        """
        Fit the 9-point piecewise affine mesh model from anchor samples.
        """
        # Verify sufficient samples for all 9 anchors (at least 8 frames per anchor)
        valid_anchors = sum(1 for idx, samples in self.anchor_samples.items() if len(samples) >= 6)
        if valid_anchors < 9:
            print(f"[Calibrator] Warning: Only {valid_anchors}/9 anchors have sufficient samples. Need all 9.")
            return False

        gaze_centers = []
        screen_pts = []

        for idx, (name, norm_x, norm_y, desc) in enumerate(CALIB_ANCHORS_9):
            samples_arr = np.array(self.anchor_samples[idx])  # (N, 4)
            # Use median for outlier rejection
            med_gx = float(np.median(samples_arr[:, 0]))
            med_gy = float(np.median(samples_arr[:, 1]))
            gaze_centers.append([med_gx, med_gy])

            px = norm_x * screen_w
            py = norm_y * screen_h
            screen_pts.append([px, py])

            # Lock baseline head pose from Center Anchor (idx 0)
            if idx == 0:
                self.base_yaw = float(np.median(samples_arr[:, 2]))
                self.base_pitch = float(np.median(samples_arr[:, 3]))

        self.anchor_gaze_centers = np.array(gaze_centers, dtype=np.float32)  # (9, 2)
        self.anchor_screen_pts = np.array(screen_pts, dtype=np.float32)      # (9, 2)

        # Solve 8 piecewise affine transformation matrices
        affines = []
        for (i0, i1, i2) in TRIANGLE_INDICES:
            src_tri = self.anchor_gaze_centers[[i0, i1, i2], :]  # (3, 2)
            dst_tri = self.anchor_screen_pts[[i0, i1, i2], :]    # (3, 2)
            M = solve_affine_2d(src_tri, dst_tri)               # (2, 3)
            affines.append(M)

        self.triangle_affines = affines
        self.is_calibrated = True

        print(f"[Calibrator] 9-Point Piecewise Affine Mesh Solved! BaseYaw={math.degrees(self.base_yaw):.1f}°, BasePitch={math.degrees(self.base_pitch):.1f}°")
        self.save()
        return True

    def predict(self, frame: ARFaceFrame, screen_w: int = 1920, screen_h: int = 1080) -> Tuple[float, float]:
        """
        Estimate 2D Screen Position using 9-Point Piecewise Affine Mesh + Head-Gaze Hybrid Boost.
        """
        if not self.is_calibrated or self.anchor_gaze_centers is None or self.triangle_affines is None:
            return self.geometry.estimate_raw_screen_pos(frame)

        # 1. Extract Primary Gaze Ray Tangent Slope
        eye_origin, v_world = self.geometry.compute_world_gaze_ray(frame)
        z_denom = abs(v_world[2]) if abs(v_world[2]) > 1e-3 else 1.0
        gx = float(v_world[0] / z_denom)
        gy = float(v_world[1] / z_denom)
        pt_gaze = np.array([gx, gy], dtype=np.float32)

        # 2. Find enclosing triangle in gaze space
        chosen_M = None
        min_dist_to_center = 1e9

        for t_idx, (i0, i1, i2) in enumerate(TRIANGLE_INDICES):
            v0 = self.anchor_gaze_centers[i0]
            v1 = self.anchor_gaze_centers[i1]
            v2 = self.anchor_gaze_centers[i2]

            if point_in_triangle_2d(pt_gaze, v0, v1, v2):
                chosen_M = self.triangle_affines[t_idx]
                break

        # Fallback if outside all triangles (extrapolation): pick the nearest triangle centroid
        if chosen_M is None:
            best_idx = 0
            best_dist = 1e9
            for t_idx, (i0, i1, i2) in enumerate(TRIANGLE_INDICES):
                centroid = np.mean(self.anchor_gaze_centers[[i0, i1, i2]], axis=0)
                d = float(np.linalg.norm(pt_gaze - centroid))
                if d < best_dist:
                    best_dist = d
                    best_idx = t_idx
            chosen_M = self.triangle_affines[best_idx]

        # 3. Apply Affine Transformation: [x, y]^T = M @ [gx, gy, 1]^T
        pt_homo = np.array([gx, gy, 1.0], dtype=np.float32)
        mapped_pos = chosen_M @ pt_homo
        screen_x = float(mapped_pos[0])
        screen_y = float(mapped_pos[1])

        # 4. Apply Head-Gaze Hybrid Boost (Tobii Extended View style)
        if self.hybrid_boost_enabled and self.hybrid_boost_gain > 0.01:
            cx = screen_w * 0.5
            cy = screen_h * 0.5

            # Normalized distance from center (0.0 at center, 1.0 at screen edge)
            dx_norm = (screen_x - cx) / (screen_w * 0.5)
            dy_norm = (screen_y - cy) / (screen_h * 0.5)
            r_norm = math.sqrt(dx_norm * dx_norm + dy_norm * dy_norm)

            # Smoothstep activation: 0% at inner 25%, ramps up smoothly to 100% at outer 85%
            if r_norm > 0.25:
                t = max(0.0, min(1.0, (r_norm - 0.25) / 0.60))
                blend = t * t * (3.0 - 2.0 * t)

                yaw, pitch, roll = quaternion_to_euler_angles(frame.head_rot)
                rel_yaw = yaw - self.base_yaw
                rel_pitch = pitch - self.base_pitch

                # If looking towards horizontal edge and turning head towards that edge:
                if (dx_norm * rel_yaw) > 0.002:
                    screen_x += rel_yaw * 1200.0 * self.hybrid_boost_gain * blend

                # If looking towards vertical edge and tilting head towards that edge:
                if (dy_norm * (-rel_pitch)) > 0.002:
                    screen_y += (-rel_pitch) * 1200.0 * self.hybrid_boost_gain * blend

        # Clamp safely within screen margin
        margin = 120.0
        screen_x = max(-margin, min(float(screen_w) + margin, screen_x))
        screen_y = max(-margin, min(float(screen_h) + margin, screen_y))

        return screen_x, screen_y

    def save(self):
        """Save 9-point piecewise affine model to disk"""
        if not self.is_calibrated or self.anchor_gaze_centers is None or self.triangle_affines is None:
            return

        data = {
            "version": "3.0_mesh_affine",
            "anchor_gaze_centers": self.anchor_gaze_centers.tolist(),
            "anchor_screen_pts": self.anchor_screen_pts.tolist(),
            "triangle_affines": [M.tolist() for M in self.triangle_affines],
            "base_yaw": self.base_yaw,
            "base_pitch": self.base_pitch,
            "hybrid_boost_gain": self.hybrid_boost_gain,
        }
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"[Calibrator] Model saved to {self.save_path}")
        except Exception as e:
            print(f"[Calibrator] Failed to save calibration: {e}")

    def load(self) -> bool:
        """Load 9-point piecewise affine model from disk with validation"""
        if not os.path.exists(self.save_path):
            return False

        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("version") != "3.0_mesh_affine":
                print(f"[Calibrator] Found older format ({data.get('version', 'legacy')}). Recalibration recommended.")
                return False

            self.anchor_gaze_centers = np.array(data["anchor_gaze_centers"], dtype=np.float32)
            self.anchor_screen_pts = np.array(data["anchor_screen_pts"], dtype=np.float32)
            self.triangle_affines = [np.array(M, dtype=np.float32) for M in data["triangle_affines"]]
            self.base_yaw = float(data.get("base_yaw", 0.0))
            self.base_pitch = float(data.get("base_pitch", 0.0))
            self.hybrid_boost_gain = float(data.get("hybrid_boost_gain", 1.0))

            if len(self.anchor_gaze_centers) == 9 and len(self.triangle_affines) == 8:
                self.is_calibrated = True
                print(f"[Calibrator] Loaded 9-Point Piecewise Affine Mesh from {self.save_path}")
                return True
        except Exception as e:
            print(f"[Calibrator] Load error: {e}")

        return False
