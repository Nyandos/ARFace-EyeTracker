import json
import os
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from .protocol import ARFaceFrame
from .geometry import GeometryEstimator

@dataclass
class CalibTarget:
    screen_pos: Tuple[float, float]
    instruction: str
    stage_name: str
    duration: float = 1.2

class Calibrator:
    """
    Multi-Dimensional 3D Head-Pose Invariant Calibration System.
    Samples gaze across varied head rotations and positions to decouple head motion from gaze.
    """
    def __init__(self, geometry: GeometryEstimator, save_path: str = "calibration_data.json"):
        self.geometry = geometry
        self.save_path = save_path
        self.is_calibrated = False

        # Samples buffer: target_idx -> list of feature arrays
        self.samples: Dict[int, List[np.ndarray]] = {}
        self.target_list: List[CalibTarget] = []

        # Model weights (Ridge Regression)
        self.poly_weights_x: Optional[np.ndarray] = None
        self.poly_weights_y: Optional[np.ndarray] = None

        self.load()

    def get_multi_pose_targets(self, width: int, height: int) -> List[CalibTarget]:
        """
        Generates a 2-stage multi-dimensional calibration schedule:
        Stage 1: 9 Natural Grid Points (Neutral Head Pose)
        Stage 2: 4 Dynamic Head Pose compensations (Center target with head tilt Left/Right/Up/Down)
        """
        margin_x = width * 0.12
        margin_y = height * 0.12
        mid_x = width * 0.5
        mid_y = height * 0.5
        max_x = width - margin_x
        max_y = height - margin_y

        targets: List[CalibTarget] = [
            # Stage 1: Natural 9-Point Grid
            CalibTarget((mid_x, mid_y), "Natural Pose — Look at center target", "STAGE 1: GRID MATRIX", 1.2),
            CalibTarget((margin_x, margin_y), "Look at Top-Left target", "STAGE 1: GRID MATRIX", 1.1),
            CalibTarget((max_x, margin_y), "Look at Top-Right target", "STAGE 1: GRID MATRIX", 1.1),
            CalibTarget((margin_x, max_y), "Look at Bottom-Left target", "STAGE 1: GRID MATRIX", 1.1),
            CalibTarget((max_x, max_y), "Look at Bottom-Right target", "STAGE 1: GRID MATRIX", 1.1),
            CalibTarget((mid_x, margin_y), "Look at Top-Center target", "STAGE 1: GRID MATRIX", 1.1),
            CalibTarget((mid_x, max_y), "Look at Bottom-Center target", "STAGE 1: GRID MATRIX", 1.1),
            CalibTarget((margin_x, mid_y), "Look at Mid-Left target", "STAGE 1: GRID MATRIX", 1.1),
            CalibTarget((max_x, mid_y), "Look at Mid-Right target", "STAGE 1: GRID MATRIX", 1.1),

            # Stage 2: 3D Head-Pose Decoupling (Keep eyes locked on center, tilt head)
            CalibTarget((mid_x, mid_y), "Keep eyes on center, tilt/turn head slightly LEFT ◀", "STAGE 2: HEAD ROTATION DECOUPLING", 1.4),
            CalibTarget((mid_x, mid_y), "Keep eyes on center, tilt/turn head slightly RIGHT ▶", "STAGE 2: HEAD ROTATION DECOUPLING", 1.4),
            CalibTarget((mid_x, mid_y), "Keep eyes on center, tilt/pitch head slightly UP ▲", "STAGE 2: HEAD ROTATION DECOUPLING", 1.4),
            CalibTarget((mid_x, mid_y), "Keep eyes on center, tilt/pitch head slightly DOWN ▼", "STAGE 2: HEAD ROTATION DECOUPLING", 1.4),
        ]
        return targets

    def reset_samples(self, target_list: List[CalibTarget]):
        self.samples.clear()
        self.target_list = target_list
        for i in range(len(target_list)):
            self.samples[i] = []

    def add_sample(self, target_idx: int, frame: ARFaceFrame):
        features = self.geometry.extract_features(frame)
        if target_idx in self.samples:
            self.samples[target_idx].append(features)

    def _expand_poly(self, feat_matrix: np.ndarray) -> np.ndarray:
        """
        High-dimensional polynomial basis including head-decoupling interaction terms.
        feat_matrix cols:
        0: gaze_tan_x (world)
        1: gaze_tan_y (world)
        2,3,4: v_world
        5,6,7: eye_origin (hx, hy, hz)
        8,9,10: yaw, pitch, roll
        """
        gx = feat_matrix[:, 0]
        gy = feat_matrix[:, 1]
        hx = feat_matrix[:, 5]
        hy = feat_matrix[:, 6]
        yaw = feat_matrix[:, 8]
        pitch = feat_matrix[:, 9]

        terms = [
            np.ones_like(gx),
            # Pure Gaze terms
            gx, gy,
            gx**2, gy**2, gx * gy,
            gx**3, gy**3,
            # Head translation & rotation cancellation terms
            hx, hy,
            yaw, pitch,
            # Cross interaction terms (Cancels gaze shift when head turns)
            gx * yaw, gy * pitch,
            gx * hx, gy * hy,
            yaw * hx, pitch * hy
        ]
        return np.column_stack(terms)

    def fit(self) -> bool:
        all_X = []
        all_Yx = []
        all_Yy = []

        for p_idx, feat_list in self.samples.items():
            if len(feat_list) < 3:
                continue
            feats = np.array(feat_list)
            # Remove top/bottom outliers based on median distance
            med = np.median(feats, axis=0)
            dists = np.linalg.norm(feats - med, axis=1)
            keep_mask = dists <= np.percentile(dists, 80)
            valid_feats = feats[keep_mask] if np.sum(keep_mask) > 0 else feats

            mean_feat = np.mean(valid_feats, axis=0)
            target = self.target_list[p_idx].screen_pos

            all_X.append(mean_feat)
            all_Yx.append(target[0])
            all_Yy.append(target[1])

        if len(all_X) < 4:
            print("[Calibrator] Insufficient points for multi-pose fit.")
            return False

        X = np.array(all_X)
        Yx = np.array(all_Yx)
        Yy = np.array(all_Yy)

        Phi = self._expand_poly(X)
        reg_lambda = 0.05
        I = np.eye(Phi.shape[1])
        self.poly_weights_x = np.linalg.solve(Phi.T @ Phi + reg_lambda * I, Phi.T @ Yx)
        self.poly_weights_y = np.linalg.solve(Phi.T @ Phi + reg_lambda * I, Phi.T @ Yy)

        self.is_calibrated = True
        self.save()
        return True

    def predict(self, frame: ARFaceFrame) -> Tuple[float, float]:
        if not self.is_calibrated or self.poly_weights_x is None:
            return self.geometry.estimate_raw_screen_pos(frame)

        feat = self.geometry.extract_features(frame).reshape(1, -1)
        phi = self._expand_poly(feat)

        px = float(phi @ self.poly_weights_x)
        py = float(phi @ self.poly_weights_y)

        margin = 150.0
        px = float(np.clip(px, -margin, self.geometry.screen_width + margin))
        py = float(np.clip(py, -margin, self.geometry.screen_height + margin))

        return px, py

    def save(self):
        if not self.is_calibrated:
            return
        data = {
            "screen_width": self.geometry.screen_width,
            "screen_height": self.geometry.screen_height,
            "poly_weights_x": self.poly_weights_x.tolist() if self.poly_weights_x is not None else [],
            "poly_weights_y": self.poly_weights_y.tolist() if self.poly_weights_y is not None else [],
            "is_calibrated": True
        }
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"[Calibrator] Multi-pose calibration model saved to {self.save_path}")
        except Exception as e:
            print(f"[Calibrator] Error saving: {e}")

    def load(self):
        if not os.path.exists(self.save_path):
            return
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.poly_weights_x = np.array(data["poly_weights_x"], dtype=np.float64)
            self.poly_weights_y = np.array(data["poly_weights_y"], dtype=np.float64)
            self.is_calibrated = True
            print(f"[Calibrator] Loaded multi-pose calibration model from {self.save_path}")
        except Exception as e:
            print(f"[Calibrator] Could not load: {e}")
