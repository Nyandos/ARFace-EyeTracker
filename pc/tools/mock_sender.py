import os
import sys
import time
import socket
import math
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.protocol import ARFaceFrame, pack_binary_frame

def run_mock_sender(host: str = "127.0.0.1", port: int = 5005, target_fps: float = 60.0, mode: str = "json"):
    """
    Simulates an iOS TrueDepth ARFaceAnchor UDP sender (Binary ARF1 or Raw JSON).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[MockSender] Sending simulated ARKit TrueDepth packets ({mode.upper()}) to {host}:{port} @ {target_fps} FPS")
    print("[MockSender] Press Ctrl+C to stop.")

    # Enable 1ms Windows timer resolution
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass

    start_time = time.perf_counter()
    interval = 1.0 / target_fps
    next_send_time = start_time
    seq = 0

    try:
        while True:
            t = time.perf_counter() - start_time

            # 1. Simulate head slight sway
            hx = 0.02 * math.sin(t * 0.5)
            hy = 0.01 * math.cos(t * 0.7)
            hz = 0.45 + 0.02 * math.sin(t * 0.3)
            head_pos = np.array([hx, hy, hz], dtype=np.float32)

            # 2. Simulate head rotation (quaternion)
            pitch = 0.05 * math.sin(t * 0.5)
            yaw = 0.08 * math.cos(t * 0.4)
            roll = 0.02 * math.sin(t * 0.6)

            cy = math.cos(yaw * 0.5)
            sy = math.sin(yaw * 0.5)
            cp = math.cos(pitch * 0.5)
            sp = math.sin(pitch * 0.5)
            cr = math.cos(roll * 0.5)
            sr = math.sin(roll * 0.5)

            qw = cr * cp * cy + sr * sp * sy
            qx = sr * cp * cy - cr * sp * sy
            qy = cr * sp * cy + sr * cp * sy
            qz = cr * cp * sy - sr * sp * cy
            head_rot = np.array([qx, qy, qz, qw], dtype=np.float32)

            # 3. Simulate Gaze scanning motion across the screen
            lx = 0.08 * math.sin(t * 1.5) + 0.03 * math.sin(t * 4.0)
            ly = 0.05 * math.cos(t * 1.2) + 0.02 * math.cos(t * 3.5)
            lz = 0.0
            look_at = np.array([lx, ly, lz], dtype=np.float32)

            # Gaze direction vectors
            left_gaze = np.array([lx - 0.03, ly, -hz], dtype=np.float32)
            left_gaze /= np.linalg.norm(left_gaze)
            right_gaze = np.array([lx + 0.03, ly, -hz], dtype=np.float32)
            right_gaze /= np.linalg.norm(right_gaze)

            # Occasional blink every 4 seconds
            blink = 1.0 if (int(t) % 4 == 0 and (t % 1.0) < 0.15) else 0.0

            if mode.lower() == "json":
                # Simulated Raw JSON payload identical to ARFaceTrackerApp
                payload = {
                    "timestamp": time.time(),
                    "head": {
                        "position": [round(float(x), 4) for x in head_pos],
                        "rotation": [round(float(x), 4) for x in head_rot],
                        "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, round(hx, 4), round(hy, 4), round(hz, 4), 1]
                    },
                    "leftEye": {
                        "lookDirection": [round(float(x), 4) for x in left_gaze],
                        "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
                    },
                    "rightEye": {
                        "lookDirection": [round(float(x), 4) for x in right_gaze],
                        "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
                    },
                    "lookAtPoint": [round(float(x), 4) for x in look_at],
                    "blendShapes": {
                        "eyeBlinkLeft": round(blink, 4),
                        "eyeBlinkRight": round(blink, 4),
                        "eyeLookInLeft": round(max(0.0, -lx * 2.0), 4),
                        "eyeLookOutLeft": round(max(0.0, lx * 2.0), 4),
                        "eyeLookUpLeft": round(max(0.0, ly * 2.0), 4),
                        "eyeLookDownLeft": round(max(0.0, -ly * 2.0), 4),
                        "eyeLookInRight": round(max(0.0, lx * 2.0), 4),
                        "eyeLookOutRight": round(max(0.0, -lx * 2.0), 4),
                        "eyeLookUpRight": round(max(0.0, ly * 2.0), 4),
                        "eyeLookDownRight": round(max(0.0, -ly * 2.0), 4),
                    }
                }
                packet = json.dumps(payload).encode('utf-8')
            else:
                frame = ARFaceFrame(
                    timestamp=t,
                    head_pos=head_pos,
                    head_rot=head_rot,
                    left_gaze=left_gaze,
                    right_gaze=right_gaze,
                    look_at_point=look_at,
                    blink_left=blink,
                    blink_right=blink
                )
                packet = pack_binary_frame(frame)

            sock.sendto(packet, (host, port))
            seq += 1

            next_send_time += interval
            sleep_dur = next_send_time - time.perf_counter()
            if sleep_dur > 0.001:
                time.sleep(sleep_dur)
            while time.perf_counter() < next_send_time:
                pass
    except KeyboardInterrupt:
        print("\n[MockSender] Stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock ARKit Face/Eye UDP Streamer")
    parser.add_argument("--mode", choices=["json", "binary"], default="json", help="Packet mode (json or binary)")
    parser.add_argument("--ip", default="127.0.0.1", help="Target PC IP")
    parser.add_argument("--port", type=int, default=5005, help="Target Port")
    parser.add_argument("--fps", type=float, default=60.0, help="Stream FPS")
    args = parser.parse_args()

    run_mock_sender(host=args.ip, port=args.port, target_fps=args.fps, mode=args.mode)
