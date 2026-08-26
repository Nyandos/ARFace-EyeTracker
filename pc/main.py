import sys
import os

# Optimize Windows Timer Resolution to 1ms for ultra-low latency 60Hz-240Hz tracking
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
from screeninfo import get_monitors

from core.protocol import ARFaceFrame
from core.receiver import UDPReceiver
from core.geometry import GeometryEstimator
from core.calibrator import Calibrator
from ui.hud_overlay import HUDOverlay
from ui.calib_window import CalibrationWindow
from ui.control_panel import ControlPanel

def get_primary_screen_size():
    try:
        monitors = get_monitors()
        for m in monitors:
            if m.is_primary:
                return m.width, m.height
        if monitors:
            return monitors[0].width, monitors[0].height
    except Exception:
        pass
    return 1920, 1080

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    screen_w, screen_h = get_primary_screen_size()
    print(f"[Main] Primary Screen Detected: {screen_w}x{screen_h}")

    # Core components
    geometry = GeometryEstimator(screen_width=screen_w, screen_height=screen_h)
    calibrator = Calibrator(geometry=geometry, save_path=os.path.join(os.path.dirname(__file__), "calibration_data.json"))
    receiver = UDPReceiver(host="0.0.0.0", port=5005)

    # UI Windows
    hud = HUDOverlay(screen_width=screen_w, screen_height=screen_h)
    calib_win = CalibrationWindow(calibrator=calibrator, screen_width=screen_w, screen_height=screen_h)
    control_panel = ControlPanel(receiver=receiver, calibrator=calibrator, hud=hud, calib_win=calib_win, geometry=geometry)

    # Pipeline hook
    def on_frame_received(frame: ARFaceFrame):
        # 1. Feed frame to calibration window if active
        if calib_win.is_active:
            calib_win.handle_frame(frame)

        # 2. Predict screen coordinates
        px, py = calibrator.predict(frame)

        # 3. Update HUD pointer
        hud.update_gaze(px, py, frame)

    receiver.register_callback(on_frame_received)

    # Start network receiver thread
    receiver.start()

    # Show HUD and Control Panel
    hud.show()
    control_panel.show()

    exit_code = app.exec()
    receiver.stop()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
