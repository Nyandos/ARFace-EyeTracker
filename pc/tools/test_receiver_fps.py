import sys
import os
import time
import threading
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.protocol import ARFaceFrame, pack_binary_frame
from core.receiver import UDPReceiver
from tools.mock_sender import run_mock_sender

def test_receiver_fps():
    port = 5011
    receiver = UDPReceiver(host="127.0.0.1", port=port)
    assert receiver.start(), "Failed to start receiver"

    received_frames = []
    receiver.register_callback(lambda f: received_frames.append(f))

    # Run mock sender in a thread for 2 seconds at 60 FPS (binary mode)
    sender_thread = threading.Thread(
        target=lambda: run_mock_sender(host="127.0.0.1", port=port, target_fps=60.0, mode="binary"),
        daemon=True
    )
    sender_thread.start()

    time.sleep(2.0)
    fps = receiver.fps
    pkt_count = receiver.packet_count
    pkt_size = receiver.last_packet_size
    jitter = receiver.jitter_ms

    receiver.stop()

    print(f"\n--- Receiver Test Results ---")
    print(f"Packets received: {pkt_count}")
    print(f"Callback dispatched: {len(received_frames)}")
    print(f"Measured FPS: {fps:.1f} FPS")
    print(f"Packet Size: {pkt_size} Bytes")
    print(f"Jitter: {jitter:.2f} ms")

    assert pkt_count > 80, f"Expected > 80 packets in 2s, got {pkt_count}"
    assert pkt_size == 84, f"Expected 84 bytes binary, got {pkt_size}"
    assert fps >= 55.0, f"Expected >= 55 FPS, got {fps:.1f}"
    print("\n>>> 60FPS RECEIVER TEST PASSED! <<<")

if __name__ == "__main__":
    test_receiver_fps()
