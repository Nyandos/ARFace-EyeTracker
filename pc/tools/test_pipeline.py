import os
import sys
import math
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
    assert len(feat) == 13, f"Expected 13 features, got {len(feat)}"
    raw_x, raw_y = geo.estimate_raw_screen_pos(frame)
    print(f"[OK] Raw projection coordinates: ({raw_x:.1f}, {raw_y:.1f})")

    gfilter = GazePointFilter()
    fx, fy = gfilter.filter(raw_x, raw_y, time.perf_counter())
    assert abs(fx - raw_x) < 1e-3
    print("[OK] Filter initialized and filtered successfully.")

    print("\n=== 3. Test 9-Point Piecewise Affine Mesh Calibration ===")
    from core.calibrator import CALIB_ANCHORS_9
    calibrator = Calibrator(geometry=geo, save_path="test_calib.json")
    calibrator.reset_dynamic_samples()

    # 1. Feed simulated anchor gaze samples for all 9 points
    for idx, (tag, norm_x, norm_y, desc) in enumerate(CALIB_ANCHORS_9):
        sim_gx = (norm_x - 0.5) * 0.40
        sim_gy = (0.5 - norm_y) * 0.30
        for _ in range(12):
            sim_frame = ARFaceFrame(
                timestamp=time.perf_counter(),
                head_pos=np.array([0.0, 0.0, 0.45], dtype=np.float32),
                head_rot=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
                left_gaze=np.array([sim_gx, sim_gy, -1.0], dtype=np.float32),
                right_gaze=np.array([sim_gx, sim_gy, -1.0], dtype=np.float32),
                look_at_point=np.array([sim_gx * 0.5, sim_gy * 0.5, 0.0], dtype=np.float32),
                blink_left=0.0,
                blink_right=0.0
            )
            calibrator.add_anchor_sample(idx, sim_frame)

    success = calibrator.fit(1920, 1080)
    assert success, "Calibrator fit failed"
    print("[OK] 9-Point Piecewise Affine Mesh model fitted and saved successfully.")

    # 2. Test mathematical 0-error property at Anchor Points!
    # Test Center (idx 0: 960, 540)
    center_frame = ARFaceFrame(
        timestamp=time.perf_counter(),
        head_pos=np.array([0.0, 0.0, 0.45], dtype=np.float32),
        head_rot=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        left_gaze=np.array([0.0, 0.0, -1.0], dtype=np.float32),
        right_gaze=np.array([0.0, 0.0, -1.0], dtype=np.float32),
        look_at_point=np.array([0.0, 0.0, 0.0], dtype=np.float32),
        blink_left=0.0, blink_right=0.0
    )
    px, py = calibrator.predict(center_frame, 1920, 1080)
    print(f"[OK] Center prediction: ({px:.1f}, {py:.1f}) [Expected exactly 960.0, 540.0]")
    assert abs(px - 960.0) < 5.0 and abs(py - 540.0) < 5.0

    # Test Top-Right (idx 2: 1824, 54)
    tr_gx = (0.95 - 0.5) * 0.40
    tr_gy = (0.5 - 0.05) * 0.30
    tr_frame = ARFaceFrame(
        timestamp=time.perf_counter(),
        head_pos=np.array([0.0, 0.0, 0.45], dtype=np.float32),
        head_rot=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        left_gaze=np.array([tr_gx, tr_gy, -1.0], dtype=np.float32),
        right_gaze=np.array([tr_gx, tr_gy, -1.0], dtype=np.float32),
        look_at_point=np.array([tr_gx * 0.5, tr_gy * 0.5, 0.0], dtype=np.float32),
        blink_left=0.0, blink_right=0.0
    )
    tr_x, tr_y = calibrator.predict(tr_frame, 1920, 1080)
    print(f"[OK] Top-Right Corner prediction: ({tr_x:.1f}, {tr_y:.1f}) [Expected exactly 1824.0, 54.0]")
    assert abs(tr_x - 1824.0) < 5.0 and abs(tr_y - 54.0) < 5.0

    # 3. Test Head-Gaze Hybrid Boost
    boost_q = np.array([0.0, np.sin(0.04), 0.0, np.cos(0.04)], dtype=np.float32)
    boost_frame = ARFaceFrame(
        timestamp=time.perf_counter(),
        head_pos=np.array([0.0, 0.0, 0.45], dtype=np.float32),
        head_rot=boost_q,
        left_gaze=np.array([tr_gx, tr_gy, -1.0], dtype=np.float32),
        right_gaze=np.array([tr_gx, tr_gy, -1.0], dtype=np.float32),
        look_at_point=np.array([tr_gx * 0.5, tr_gy * 0.5, 0.0], dtype=np.float32),
        blink_left=0.0, blink_right=0.0
    )
    calibrator.hybrid_boost_gain = 1.0
    b_on_x, b_on_y = calibrator.predict(boost_frame, 1920, 1080)
    calibrator.hybrid_boost_gain = 0.0
    b_off_x, b_off_y = calibrator.predict(boost_frame, 1920, 1080)
    print(f"[OK] Hybrid Head-Gaze Boost: X moved from {b_off_x:.1f} (Off) to {b_on_x:.1f} (Boosted!)")
    assert b_on_x > b_off_x
    calibrator.hybrid_boost_gain = 1.0

    print("\n=== 4. Test UDPReceiver & FacePreviewWidget Import ===")
    from core.receiver import UDPReceiver
    rcv = UDPReceiver(port=5007)
    assert rcv.start()
    time.sleep(0.05)
    rcv.stop()
    print("[OK] UDPReceiver started and stopped cleanly.")

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.face_preview import FacePreviewWidget
    fp = FacePreviewWidget()
    fp.update_frame(frame)
    assert fp.is_tracking
    assert abs(fp.pitch_deg) < 1.0
    print("[OK] FacePreviewWidget initialized and updated frame.")

    print("\n=== 5. Test CalibrationWindow Phase 2 Baseline Lock & Advance ===")
    from ui.calib_window import CalibrationWindow, CalibState
    cw = CalibrationWindow(calibrator, 1920, 1080)
    print("\n=== 5. Test CalibrationWindow 9-Point Anchor Sequence ===")
    from ui.calib_window import CalibrationWindow, CalibState
    cw = CalibrationWindow(calibrator, 1920, 1080)
    cw.start_calibration()
    assert cw.state == CalibState.INTRO
    cw._begin_anchor_sequence()
    assert cw.state == CalibState.ANCHOR_POINT
    assert cw.current_anchor_idx == 0
    for _ in range(15):
        cw.handle_frame(frame)
    cw._advance_anchor()
    assert cw.current_anchor_idx == 1
    print("[OK] CalibrationWindow 9-Point Anchor sequence and transit verified.")

    print("\n=== 6. Test Active Mouse Calibration Sampling ===")
    cw.start_active_mouse_calibration()
    assert cw.state == CalibState.ACTIVE_MOUSE
    assert cw.active_mouse_duration == 10.0
    for _ in range(15):
        cw.handle_frame(frame)
    assert cw.total_samples == 15
    assert len(cw.mouse_trail) == 15
    print("[OK] Active Mouse Calibration sampled 15 live cursor frames cleanly.")

    print("\n=== 7. Test PnP Monitor Spatial Solver & Physical Ray-Intersection ===")
    from core.pnp_solver import solve_monitor_pnp
    corners = np.array([
        [240.0, 120.0],
        [1040.0, 120.0],
        [1000.0, 600.0],
        [280.0, 600.0]
    ], dtype=np.float32)
    pose = solve_monitor_pnp(corners, 0.531, 0.299, 1280, 720)
    assert pose is not None
    assert pose.pos_z_m > 0.20
    print(f"[OK] solve_monitor_pnp calculated: {pose.describe()}")

    # Test physical ray-plane intersection injection
    geo.set_physical_monitor_pose(
        pos_x_m=pose.pos_x_m,
        pos_y_m=pose.pos_y_m,
        pos_z_m=pose.pos_z_m,
        pitch_deg=pose.pitch_deg,
        monitor_w_m=pose.monitor_width_m,
        monitor_h_m=pose.monitor_height_m
    )
    assert geo.has_physical_pose
    p_hit = geo.compute_physical_ray_intersection(np.array([0.0, 0.1, 0.45]), np.array([0.0, 0.0, -1.0]))
    assert p_hit is not None
    print(f"[OK] Physical 3D Ray-Intersection computed on screen: ({p_hit[0]:.1f}, {p_hit[1]:.1f})")

    # Test PhotoReceiver start & stop
    from core.photo_receiver import PhotoReceiver
    pr = PhotoReceiver(port=5008)
    assert pr.start()
    pr.stop()
    print("[OK] PhotoReceiver started and stopped cleanly.")

    print("\n=== 8. Test Sensor Lab Monitor Inclinometer Ingestion ===")
    geo.set_sensor_lab_angles(
        monitor_pitch_deg=85.0,
        phone_pitch_deg=62.0,
        monitor_back_tilt_deg=5.0,
        phone_upward_tilt_deg=28.0,
        relative_angle_deg=33.0
    )
    assert abs(math.degrees(geo.pnp_pitch_rad) - 33.0) < 1e-3
    p_hit_sensor = geo.compute_physical_ray_intersection(np.array([0.0, 0.1, 0.45]), np.array([0.0, 0.0, -1.0]))
    assert p_hit_sensor is not None
    print(f"[OK] Sensor Lab ray-intersection computed: ({p_hit_sensor[0]:.1f}, {p_hit_sensor[1]:.1f})")

    # Clean up test file
    import os
    if os.path.exists("test_calib.json"):
        os.remove("test_calib.json")

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_pipeline()
