import socket
import threading
import time
from collections import deque
from typing import Optional, Callable, List
from .protocol import ARFaceFrame, unpack_packet

class UDPReceiver:
    """
    High-speed, low-latency asynchronous UDP packet receiver.
    Features:
    - 1MB OS socket buffer to prevent packet bursts from dropping.
    - Decoupled worker queue so callback execution never stalls UDP ingestion.
    - Precise sliding-window FPS & frame jitter telemetry.
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 5005):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.listen_thread: Optional[threading.Thread] = None
        self.dispatch_thread: Optional[threading.Thread] = None
        self.running = False

        self._latest_frame: Optional[ARFaceFrame] = None
        self._lock = threading.Lock()

        # Telemetry & Stats
        self.packet_count = 0
        self.last_packet_size = 0
        self.fps = 0.0
        self.jitter_ms = 0.0
        self.last_received_time = 0.0
        self._timestamps = deque(maxlen=60)  # Sliding window of last 60 frame timestamps

        # Dispatch Queue (size 2: always keep only latest to ensure zero latency)
        self._dispatch_event = threading.Event()
        self._pending_frame: Optional[ARFaceFrame] = None

        # Callbacks
        self.on_frame_callbacks: List[Callable[[ARFaceFrame], None]] = []

    def register_callback(self, callback: Callable[[ARFaceFrame], None]):
        self.on_frame_callbacks.append(callback)

    def start(self) -> bool:
        if self.running:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Expand socket buffer to 1MB (prevents burst drops over Wi-Fi)
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
            except Exception:
                pass
            self.sock.bind((self.host, self.port))
            self.sock.settimeout(0.2)  # 200ms timeout for graceful thread shutdown
            self.running = True

            # 1. Thread for high-frequency network ingestion
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True, name="UDP-Ingest")
            self.listen_thread.start()

            # 2. Dedicated thread for dispatching callbacks without blocking network socket
            self.dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True, name="Frame-Dispatch")
            self.dispatch_thread.start()

            print(f"[UDPReceiver] Listening on {self.host}:{self.port} (Buffer: 1MB, Dual-Thread)")
            return True
        except Exception as e:
            print(f"[UDPReceiver] Failed to start: {e}")
            self.stop()
            return False

    def stop(self):
        self.running = False
        self._dispatch_event.set()

        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=1.0)
        if self.dispatch_thread and self.dispatch_thread.is_alive():
            self.dispatch_thread.join(timeout=1.0)

        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        print("[UDPReceiver] Stopped.")

    def restart_on_port(self, new_port: int) -> bool:
        self.stop()
        self.port = new_port
        return self.start()

    def get_latest_frame(self) -> Optional[ARFaceFrame]:
        with self._lock:
            return self._latest_frame

    def is_connected(self) -> bool:
        return (time.perf_counter() - self.last_received_time) < 1.0

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
                recv_time = time.perf_counter()
                frame = unpack_packet(data)
                if frame is not None:
                    # Update stats
                    with self._lock:
                        self._latest_frame = frame
                        self.packet_count += 1
                        self.last_packet_size = len(data)
                        
                        # Jitter calculation
                        if self.last_received_time > 0:
                            delta = (recv_time - self.last_received_time) * 1000.0  # ms
                            self.jitter_ms = 0.9 * self.jitter_ms + 0.1 * abs(delta - (1000.0 / max(1.0, self.fps)))
                        
                        self.last_received_time = recv_time
                        self._timestamps.append(recv_time)

                        # Precise Sliding Window FPS (over last N frames)
                        if len(self._timestamps) >= 5:
                            duration = self._timestamps[-1] - self._timestamps[0]
                            if duration > 0.001:
                                self.fps = (len(self._timestamps) - 1) / duration

                        # Pass latest frame to dispatcher
                        self._pending_frame = frame
                        self._dispatch_event.set()

            except socket.timeout:
                # Normal timeout to check self.running
                if time.perf_counter() - self.last_received_time > 1.0:
                    self.fps = 0.0
                    self.jitter_ms = 0.0
            except Exception as e:
                if self.running:
                    print(f"[UDPReceiver] Ingest error: {e}")
                time.sleep(0.005)

    def _dispatch_loop(self):
        """Dispatches callbacks on a separate thread to prevent stalling network ingest"""
        while self.running:
            self._dispatch_event.wait(timeout=0.1)
            if not self.running:
                break

            frame = None
            with self._lock:
                if self._pending_frame is not None:
                    frame = self._pending_frame
                    self._pending_frame = None
                    self._dispatch_event.clear()

            if frame is not None:
                for cb in self.on_frame_callbacks:
                    try:
                        cb(frame)
                    except Exception as e:
                        print(f"[UDPReceiver] Callback error: {e}")
