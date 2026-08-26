import socket
import threading
import time
from typing import Optional, Callable
from .protocol import ARFaceFrame, unpack_packet

class UDPReceiver:
    """
    High-speed asynchronous UDP packet receiver running in a dedicated worker thread.
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 5005):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

        self._latest_frame: Optional[ARFaceFrame] = None
        self._lock = threading.Lock()

        # Stats
        self.packet_count = 0
        self.fps = 0.0
        self.last_received_time = 0.0
        self._fps_counter = 0
        self._fps_last_calc = time.perf_counter()

        # Callbacks
        self.on_frame_callbacks = []

    def register_callback(self, callback: Callable[[ARFaceFrame], None]):
        self.on_frame_callbacks.append(callback)

    def start(self) -> bool:
        if self.running:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Set socket buffer size for burst packets
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            self.sock.bind((self.host, self.port))
            self.sock.settimeout(0.2)  # 200ms timeout for graceful shutdown loop
            self.running = True

            self.thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.thread.start()
            print(f"[UDPReceiver] Listening on {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[UDPReceiver] Failed to start: {e}")
            self.stop()
            return False

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
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
        # Connected if received a packet within the last 1.0 second
        return (time.perf_counter() - self.last_received_time) < 1.0

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
                frame = unpack_packet(data)
                if frame is not None:
                    now = time.perf_counter()
                    with self._lock:
                        self._latest_frame = frame
                        self.last_received_time = now
                        self.packet_count += 1
                        self._fps_counter += 1

                    # Update FPS calculation every 0.5s
                    if now - self._fps_last_calc >= 0.5:
                        self.fps = self._fps_counter / (now - self._fps_last_calc)
                        self._fps_counter = 0
                        self._fps_last_calc = now

                    for cb in self.on_frame_callbacks:
                        try:
                            cb(frame)
                        except Exception as e:
                            print(f"[UDPReceiver] Callback error: {e}")
            except socket.timeout:
                # Normal timeout to allow loop exit check
                pass
            except Exception as e:
                if self.running:
                    print(f"[UDPReceiver] Error receiving: {e}")
                time.sleep(0.01)
