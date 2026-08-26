import io
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Callable
import numpy as np
import cv2
from PyQt6.QtCore import QObject, pyqtSignal

class PhotoReceiver(QObject):
    """
    Lightweight HTTP Server listening on port 5006 to receive monitor alignment photos
    and Sensor Lab inclination data streamed from the iPhone via HTTP POST.
    """
    photo_received = pyqtSignal(np.ndarray)  # Emits RGB numpy image array (H, W, 3)
    sensor_data_received = pyqtSignal(dict)  # Emits dict with sensor lab telemetry

    def __init__(self, port: int = 5006):
        super().__init__()
        self.port = port
        self.httpd: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False

    def start(self) -> bool:
        if self.is_running:
            return True

        receiver_ref = self

        class PhotoHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Silent logging

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ARFace-Eyetracker PhotoReceiver Ready")

            def do_POST(self):
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length > 0:
                        body_data = self.rfile.read(content_length)

                        # 1. Handle Sensor Lab JSON metrics
                        if self.path == "/upload_sensor_data" or "json" in self.headers.get('Content-Type', '').lower():
                            import json
                            data = json.loads(body_data.decode('utf-8'))
                            receiver_ref.sensor_data_received.emit(data)

                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(b'{"status": "ok", "message": "Sensor telemetry ingested successfully"}')
                            print(f"[PhotoReceiver] Ingested Sensor Lab telemetry: {data}")
                            return

                        # 2. Handle Monitor Photo Image
                        nparr = np.frombuffer(body_data, np.uint8)
                        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if img_bgr is not None:
                            img_arr = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                            # Emit on Qt thread
                            receiver_ref.photo_received.emit(img_arr)

                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.end_headers()
                            self.wfile.write(b'{"status": "ok", "message": "Photo ingested successfully"}')
                            print(f"[PhotoReceiver] Successfully received monitor photo: {img_arr.shape[1]}x{img_arr.shape[0]}")
                            return
                except Exception as e:
                    print(f"[PhotoReceiver] Error parsing incoming POST: {e}")

                self.send_response(400)
                self.end_headers()

        try:
            self.httpd = HTTPServer(("0.0.0.0", self.port), PhotoHandler)
            self.is_running = True
            self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.server_thread.start()
            print(f"[PhotoReceiver] Listening for photos on port {self.port}")
            return True
        except Exception as e:
            print(f"[PhotoReceiver] Failed to bind port {self.port}: {e}")
            self.is_running = False
            return False

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        self.is_running = False
        print("[PhotoReceiver] Stopped.")

    def load_image_from_file(self, filepath: str) -> bool:
        """Helper to load photo manually from disk"""
        if not os.path.exists(filepath):
            return False
        try:
            img_bgr = cv2.imread(filepath)
            if img_bgr is not None:
                img_arr = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                self.photo_received.emit(img_arr)
                return True
            return False
        except Exception as e:
            print(f"[PhotoReceiver] Failed to load image {filepath}: {e}")
            return False
