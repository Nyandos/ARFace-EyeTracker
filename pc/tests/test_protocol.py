import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.protocol import unpack_packet, pack_binary_frame, ARFaceFrame

def test_binary_unpack():
    print("Testing Binary Unpack...")
    frame = ARFaceFrame(
        timestamp=12345.67,
        head_pos=np.array([0.01, 0.02, 0.45], dtype=np.float32),
        head_rot=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        left_gaze=np.array([0.05, 0.02, -0.45], dtype=np.float32),
        right_gaze=np.array([0.05, 0.02, -0.45], dtype=np.float32),
        look_at_point=np.array([0.08, 0.05, 0.0], dtype=np.float32),
        blink_left=0.1,
        blink_right=0.2
    )
    binary_data = pack_binary_frame(frame)
    assert len(binary_data) == 84, f"Expected 84 bytes, got {len(binary_data)}"
    
    unpacked = unpack_packet(binary_data)
    assert unpacked is not None, "Failed to unpack binary packet"
    assert abs(unpacked.timestamp - 12345.67) < 1e-4
    assert np.allclose(unpacked.head_pos, [0.01, 0.02, 0.45], atol=1e-4)
    print("  Binary Unpack: PASS")

def test_raw_json_unpack():
    print("Testing Raw JSON Unpack...")
    payload = {
        "timestamp": 1724748123.456,
        "head": {
            "position": [0.012, -0.005, 0.452],
            "rotation": [0.01, 0.02, 0.03, 0.999],
            "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0.012, -0.005, 0.452, 1]
        },
        "leftEye": {
            "lookDirection": [0.045, -0.012, -0.998],
            "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        },
        "rightEye": {
            "lookDirection": [0.045, -0.012, -0.998],
            "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        },
        "lookAtPoint": [0.032, -0.015, 0.0],
        "blendShapes": {
            "eyeBlinkLeft": 0.0,
            "eyeBlinkRight": 0.0,
            "eyeLookInLeft": 0.12,
            "eyeLookOutRight": 0.12
        }
    }
    json_bytes = json.dumps(payload).encode('utf-8')
    unpacked = unpack_packet(json_bytes)
    assert unpacked is not None, "Failed to unpack raw json packet"
    assert abs(unpacked.timestamp - 1724748123.456) < 1e-3
    assert np.allclose(unpacked.look_at_point, [0.032, -0.015, 0.0], atol=1e-3)
    assert np.allclose(unpacked.head_pos, [0.012, -0.005, 0.452], atol=1e-3)
    assert "Raw ARKit JSON Stream" in unpacked.raw_packet_debug
    print("  Raw JSON Unpack: PASS")

if __name__ == "__main__":
    test_binary_unpack()
    test_raw_json_unpack()
    print("ALL TESTS PASSED SUCCESSFULLY!")
