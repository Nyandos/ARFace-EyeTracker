import os
import sys
import numpy as np
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.protocol import ARFaceFrame, pack_binary_frame, unpack_packet
from core.geometry import GeometryEstimator
from core.calibrator import Calibrator
from core.filter import GazePointFilter

def test_pipeline():
    print("=== 1. Test Protocol Pack / Unpack ===")
    frame = ARFaceFrame(
        timestamp=123.456,
        head_pos=np.array([0.01, 0.02, 0.45], dtype=np.float32),
        head_rot=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        left_gaze=np.array([0.0, 0.0, -1.0], dtype=np.float32),
        right_gaze=np.array([0.0, 0.0, -1.0], dtype=np.float32),
        look_at_point=np.array([0.05, 0.03, 0.0], dtype=np.float32),
        blink_left=0.0,
        blink_right=0.0
    )
    packed = pack_binary_frame(frame)
    assert len(packed) == 84, f"Expected 84 bytes, got {len(packed)}"
    unpacked = unpack_packet(packed)
    assert unpacked is not None
    assert abs(unpacked.timestamp - 123.456) < 1e-4
    assert np.allclose(unpacked.head_pos, frame.head_pos)
    print("[OK] Native binary protocol pack/unpack successful.")

    # 1-b. Test iFacialMocap Text Protocol
    ifacial_str = "=head#5.0,-10.0,2.0,1.2,-0.5,45.0|eyeLeft#-3.0,5.0,0.0|eyeRight#-3.0,5.0,0.0|eyeBlinkLeft-0.0|eyeBlinkRight-0.0|eyeLookOutLeft-0.4|eyeLookInRight-0.4"
    ifacial_frame = unpack_packet(ifacial_str.encode('utf-8'))
    assert ifacial_frame is not None, "Failed to parse iFacialMocap format"
    assert abs(ifacial_frame.head_pos[2] - 0.45) < 1e-3
    print("[OK] iFacialMocap text protocol parsed successfully.")

    # 1-c. Test Generic ARKit JSON Protocol
    json_str = '{"head": {"position": [0.02, -0.01, 0.50], "rotation": [0, 0, 0, 1]}, "blendShapes": {"eyeBlinkLeft": 0.0, "eyeLookOutLeft": 0.5, "eyeLookInRight": 0.5}}'
    json_frame = unpack_packet(json_str.encode('utf-8'))
    assert json_frame is not None, "Failed to parse ARKit JSON format"
    assert abs(json_frame.head_pos[0] - 0.02) < 1e-3
    print("[OK] Generic ARKit JSON protocol parsed successfully.")

    print("\n=== 2. Test Geometry & 1Euro Filter ===")
    geo = GeometryEstimator(1920, 1080)
    feat = geo.extract_features(frame)
    assert len(feat) == 11
    raw_x, raw_y = geo.estimate_raw_screen_pos(frame)
    print(f"[OK] Raw projection coordinates: ({raw_x:.1f}, {raw_y:.1f})")

    gfilter = GazePointFilter()
    fx, fy = gfilter.filter(raw_x, raw_y, time.perf_counter())
    assert abs(fx - raw_x) < 1e-3
    print("[OK] Filter initialized and filtered successfully.")

    print("\n=== 3. Test Multi-Pose Calibrator Simulation ===")
    calibrator = Calibrator(geometry=geo, save_path="test_calib.json")
    targets = calibrator.get_multi_pose_targets(1920, 1080)
    assert len(targets) == 13
    calibrator.reset_samples(targets)

    # Add simulated samples for each point
    for idx, target in enumerate(targets):
        tx, ty = target.screen_pos
        norm_x = tx / 1920.0
        norm_y = ty / 1080.0
        sim_lx = (norm_x - 0.5) * 0.20
        sim_ly = (0.5 - norm_y) * 0.15

        for _ in range(10):
            sim_frame = ARFaceFrame(
                timestamp=time.perf_counter(),
                head_pos=np.array([0.0, 0.0, 0.45], dtype=np.float32),
                head_rot=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
                left_gaze=np.array([0.0, 0.0, -1.0], dtype=np.float32),
                right_gaze=np.array([0.0, 0.0, -1.0], dtype=np.float32),
                look_at_point=np.array([sim_lx + np.random.normal(0, 0.002), sim_ly + np.random.normal(0, 0.002), 0.0], dtype=np.float32),
                blink_left=0.0,
                blink_right=0.0
            )
            calibrator.add_sample(idx, sim_frame)

    success = calibrator.fit()
    assert success, "Calibrator fit failed"
    print("[OK] Calibrator fit model successfully.")

    # Test prediction on center target
    center_frame = ARFaceFrame(
        timestamp=time.perf_counter(),
        head_pos=np.array([0.0, 0.0, 0.45], dtype=np.float32),
        head_rot=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        left_gaze=np.array([0.0, 0.0, -1.0], dtype=np.float32),
        right_gaze=np.array([0.0, 0.0, -1.0], dtype=np.float32),
        look_at_point=np.array([0.0, 0.0, 0.0], dtype=np.float32),
        blink_left=0.0,
        blink_right=0.0
    )
    pred_x, pred_y = calibrator.predict(center_frame)
    print(f"[OK] Center prediction: ({pred_x:.1f}, {pred_y:.1f}) [Expected ~ 960, 540]")
    assert abs(pred_x - 960) < 50
    assert abs(pred_y - 540) < 50

    # Clean up test file
    import os
    if os.path.exists("test_calib.json"):
        os.remove("test_calib.json")

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_pipeline()
