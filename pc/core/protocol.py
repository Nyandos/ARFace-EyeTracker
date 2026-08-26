import struct
import json
import math
import re
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, Dict

MAGIC_HEADER = b'ARF1'
BINARY_FORMAT = "!4sd3f4f3f3f3f2f"
BINARY_SIZE = struct.calcsize(BINARY_FORMAT)

@dataclass
class ARFaceFrame:
    timestamp: float                    # Seconds
    head_pos: np.ndarray                # [x, y, z] in meters
    head_rot: np.ndarray                # [qx, qy, qz, qw]
    left_gaze: np.ndarray               # [x, y, z] direction vector
    right_gaze: np.ndarray              # [x, y, z] direction vector
    look_at_point: np.ndarray           # [x, y, z] gaze point in meters
    blink_left: float                   # 0.0 ~ 1.0
    blink_right: float                  # 0.0 ~ 1.0
    raw_packet_debug: str = ""          # Debug raw text snippet
    raw_gaze_debug: str = ""            # Debug text: e.g. "Pitch: +12.3° Yaw: -8.1°"


def euler_to_quaternion(pitch: float, yaw: float, roll: float) -> np.ndarray:
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
    return np.array([qx, qy, qz, qw], dtype=np.float32)


def parse_ifacialmocap_packet(text: str) -> Optional[ARFaceFrame]:
    """
    Robust universal parser for iFacialMocap, FaceCap, and OSC text streams.
    Handles various delimiters: '|', ',', '\n', '\r', ';'
    """
    try:
        head_pos = np.array([0.0, 0.0, 0.45], dtype=np.float32)
        head_rot = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        
        eye_l_pitch, eye_l_yaw = 0.0, 0.0
        eye_r_pitch, eye_r_yaw = 0.0, 0.0
        has_left_eye = False
        has_right_eye = False

        blendshapes: Dict[str, float] = {}

        # Split by pipe, newline or semicolon
        tokens = re.split(r'[|\r\n;]+', text.strip())

        for token in tokens:
            token = token.strip()
            if not token:
                continue

            # 1. Head Pose: =head#p,y,r,x,y,z or head#...
            if "head#" in token.lower():
                try:
                    val_str = token.split("#")[1]
                    vals = [float(v) for v in val_str.split(",") if v.strip()]
                    if len(vals) >= 6:
                        p_deg, y_deg, r_deg, hx, hy, hz = vals[:6]
                        pitch = math.radians(p_deg)
                        yaw = math.radians(y_deg)
                        roll = math.radians(r_deg)
                        head_rot = euler_to_quaternion(pitch, yaw, roll)

                        if abs(hz) > 5.0:  # cm scale
                            head_pos = np.array([hx / 100.0, hy / 100.0, hz / 100.0], dtype=np.float32)
                        else:
                            head_pos = np.array([hx, hy, hz], dtype=np.float32)
                except Exception:
                    pass

            # 2. Eye Rotation: eyeLeft#p,y,r or leftEye#...
            elif "eyeleft#" in token.lower() or "lefteye#" in token.lower():
                try:
                    val_str = token.split("#")[1]
                    vals = [float(v) for v in val_str.split(",") if v.strip()]
                    if len(vals) >= 2:
                        eye_l_pitch = vals[0]
                        eye_l_yaw = vals[1]
                        has_left_eye = True
                except Exception:
                    pass

            elif "eyeright#" in token.lower() or "righteye#" in token.lower():
                try:
                    val_str = token.split("#")[1]
                    vals = [float(v) for v in val_str.split(",") if v.strip()]
                    if len(vals) >= 2:
                        eye_r_pitch = vals[0]
                        eye_r_yaw = vals[1]
                        has_right_eye = True
                except Exception:
                    pass

            # 3. Blendshapes: key-val or key=val or key:val (e.g. eyeBlinkLeft-0.5, eyeLookIn_L-0.3)
            elif "-" in token or "=" in token or ":" in token:
                clean_tok = token.replace("=", "-").replace(":", "-")
                if "-" in clean_tok:
                    parts = clean_tok.split("-", 1)
                    if len(parts) == 2:
                        k = parts[0].strip().lower().replace("_", "")
                        v_str = parts[1].strip()
                        try:
                            val_f = float(v_str)
                            blendshapes[k] = val_f / 100.0 if val_f > 1.0 else val_f
                        except ValueError:
                            pass

        # -------------------------------------------------------------
        # Fuse Gaze from Eye Rotations & Blendshapes
        # -------------------------------------------------------------
        # A. Eye Rotation Angles (Direct Gaze Vector)
        if has_left_eye or has_right_eye:
            if has_left_eye and has_right_eye:
                avg_yaw = (eye_l_yaw + eye_r_yaw) * 0.5
                avg_pitch = (eye_l_pitch + eye_r_pitch) * 0.5
            elif has_left_eye:
                avg_yaw = eye_l_yaw
                avg_pitch = eye_l_pitch
            else:
                avg_yaw = eye_r_yaw
                avg_pitch = eye_r_pitch

            # Convert degree rotation (-30° ~ +30°) to normalized span (-1.0 ~ +1.0)
            # 20 degrees eye rotation is roughly full screen span
            rot_gaze_x = math.tan(math.radians(avg_yaw)) * 2.8
            rot_gaze_y = -math.tan(math.radians(avg_pitch)) * 2.8
            has_rot = True
        else:
            rot_gaze_x, rot_gaze_y = 0.0, 0.0
            avg_yaw, avg_pitch = 0.0, 0.0
            has_rot = False

        # B. BlendShapes (Fuzzy lookup)
        def get_bs(*keys):
            for k in keys:
                k_clean = k.lower().replace("_", "")
                if k_clean in blendshapes:
                    return blendshapes[k_clean]
            return 0.0

        look_in_l = get_bs("eyelookinleft", "eyelookinl", "lookinleft")
        look_out_l = get_bs("eyelookoutleft", "eyelookoutl", "lookoutleft")
        look_up_l = get_bs("eyelookupleft", "eyelookupl", "lookupleft")
        look_down_l = get_bs("eyelookdownleft", "eyelookdownl", "lookdownleft")

        look_in_r = get_bs("eyelookinright", "eyelookinr", "lookinright")
        look_out_r = get_bs("eyelookoutright", "eyelookoutr", "lookoutright")
        look_up_r = get_bs("eyelookupright", "eyelookupr", "lookupright")
        look_down_r = get_bs("eyelookdownright", "eyelookdownr", "lookdownright")

        bs_gaze_x = ((look_out_l - look_in_l) + (look_in_r - look_out_r)) * 1.2
        bs_gaze_y = (((look_up_l + look_up_r) * 0.5) - ((look_down_l + look_down_r) * 0.5)) * 1.5
        has_bs = (abs(bs_gaze_x) > 0.005 or abs(bs_gaze_y) > 0.005)

        # Fuse
        if has_rot:
            final_gaze_x = rot_gaze_x
            final_gaze_y = rot_gaze_y
            if has_bs:
                final_gaze_x = 0.6 * rot_gaze_x + 0.4 * bs_gaze_x
                final_gaze_y = 0.6 * rot_gaze_y + 0.4 * bs_gaze_y
        elif has_bs:
            final_gaze_x = bs_gaze_x
            final_gaze_y = bs_gaze_y
        else:
            final_gaze_x = 0.0
            final_gaze_y = 0.0

        blink_l = get_bs("eyeblinkleft", "eyeblinkl", "blinkleft")
        blink_r = get_bs("eyeblinkright", "eyeblinkr", "blinkright")

        # Map to 3D look_at_point (meters)
        look_at_x = float(final_gaze_x * 0.22)
        look_at_y = float(final_gaze_y * 0.16)
        look_at = np.array([look_at_x, look_at_y, 0.0], dtype=np.float32)

        # 3D Gaze direction vector
        left_gaze = np.array([final_gaze_x, final_gaze_y, -1.0], dtype=np.float32)
        left_gaze /= np.linalg.norm(left_gaze)
        right_gaze = left_gaze.copy()

        debug_snippet = text[:40] + ("..." if len(text) > 40 else "")
        if has_rot:
            gaze_debug_str = f"EyeRot: Yaw={avg_yaw:+.1f}° Pitch={avg_pitch:+.1f}°"
        elif has_bs:
            gaze_debug_str = f"BlendShape: X={final_gaze_x:+.2f} Y={final_gaze_y:+.2f}"
        else:
            gaze_debug_str = "⚠️ NO EYE ROT / BLENDSHAPE FOUND"

        import time
        return ARFaceFrame(
            timestamp=time.time(),
            head_pos=head_pos,
            head_rot=head_rot,
            left_gaze=left_gaze,
            right_gaze=right_gaze,
            look_at_point=look_at,
            blink_left=blink_l,
            blink_right=blink_r,
            raw_packet_debug=debug_snippet,
            raw_gaze_debug=gaze_debug_str
        )
    except Exception as e:
        return None


def unpack_packet(data: bytes) -> Optional[ARFaceFrame]:
    """
    Universal Packet Unpacker.
    """
    # 1. Native Binary Format
    if len(data) == BINARY_SIZE and data.startswith(MAGIC_HEADER):
        try:
            unpacked = struct.unpack(BINARY_FORMAT, data)
            ts = unpacked[1]
            h_pos = np.array(unpacked[2:5], dtype=np.float32)
            h_rot = np.array(unpacked[5:9], dtype=np.float32)
            l_gaze = np.array(unpacked[9:12], dtype=np.float32)
            r_gaze = np.array(unpacked[12:15], dtype=np.float32)
            look_at = np.array(unpacked[15:18], dtype=np.float32)
            b_left = float(unpacked[18])
            b_right = float(unpacked[19])

            return ARFaceFrame(
                timestamp=ts,
                head_pos=h_pos,
                head_rot=h_rot,
                left_gaze=l_gaze,
                right_gaze=r_gaze,
                look_at_point=look_at,
                blink_left=b_left,
                blink_right=b_right,
                raw_packet_debug="Native Binary ARF1 (84 bytes)",
                raw_gaze_debug=f"LookAt: X={look_at[0]:+.2f} Y={look_at[1]:+.2f}m"
            )
        except Exception:
            return None

    # Try string decode
    try:
        text = data.decode('utf-8', errors='ignore').strip()
    except Exception:
        return None

    # 2. JSON format (if starts with {)
    if text.startswith("{") or text.endswith("}"):
        try:
            d = json.loads(text)
            if "blendShapes" in d or "BlendShapes" in d:
                bs = d.get("blendShapes", d.get("BlendShapes", {}))
                
                def get_val(*keys):
                    for k in keys:
                        if k in bs:
                            return float(bs[k])
                    return 0.0

                blink_l = get_val("eyeBlinkLeft", "eyeBlink_L", "eyeBlinkLeft_0")
                blink_r = get_val("eyeBlinkRight", "eyeBlink_R", "eyeBlinkRight_0")

                look_in_l = get_val("eyeLookInLeft", "eyeLookIn_L")
                look_out_l = get_val("eyeLookOutLeft", "eyeLookOut_L")
                look_up_l = get_val("eyeLookUpLeft", "eyeLookUp_L")
                look_down_l = get_val("eyeLookDownLeft", "eyeLookDown_L")
                look_in_r = get_val("eyeLookInRight", "eyeLookIn_R")
                look_out_r = get_val("eyeLookOutRight", "eyeLookOut_R")
                look_up_r = get_val("eyeLookUpRight", "eyeLookUp_R")
                look_down_r = get_val("eyeLookDownRight", "eyeLookDown_R")

                bs_gx = (((look_out_l - look_in_l) + (look_in_r - look_out_r)) * 0.5) * 2.5
                bs_gy = (((look_up_l + look_up_r) * 0.5) - ((look_down_l + look_down_r) * 0.5)) * 2.5

                head = d.get("head", d.get("Head", {}))
                pos = head.get("position", [0, 0, 0.45])
                rot = head.get("rotation", [0, 0, 0, 1])
                if len(rot) == 3:
                    rot = euler_to_quaternion(math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2]))
                else:
                    rot = np.array(rot, dtype=np.float32)

                # Prioritize direct TrueDepth 3D gaze vectors if available in Raw JSON
                if "lookAtPoint" in d and len(d["lookAtPoint"]) == 3:
                    look_at = np.array(d["lookAtPoint"], dtype=np.float32)
                else:
                    look_at = np.array([bs_gx * 0.20, bs_gy * 0.15, 0.0], dtype=np.float32)

                if "leftEye" in d and "lookDirection" in d["leftEye"]:
                    left_gaze = np.array(d["leftEye"]["lookDirection"], dtype=np.float32)
                    norm_l = np.linalg.norm(left_gaze)
                    if norm_l > 1e-6:
                        left_gaze /= norm_l
                else:
                    left_gaze = np.array([bs_gx, bs_gy, -1.0], dtype=np.float32)
                    left_gaze /= np.linalg.norm(left_gaze)

                if "rightEye" in d and "lookDirection" in d["rightEye"]:
                    right_gaze = np.array(d["rightEye"]["lookDirection"], dtype=np.float32)
                    norm_r = np.linalg.norm(right_gaze)
                    if norm_r > 1e-6:
                        right_gaze /= norm_r
                else:
                    right_gaze = left_gaze.copy()

                import time
                return ARFaceFrame(
                    timestamp=float(d.get("timestamp", time.time())),
                    head_pos=np.array(pos, dtype=np.float32),
                    head_rot=rot,
                    left_gaze=left_gaze,
                    right_gaze=right_gaze,
                    look_at_point=look_at,
                    blink_left=blink_l,
                    blink_right=blink_r,
                    raw_packet_debug="Raw ARKit JSON Stream",
                    raw_gaze_debug=f"LookAt: X={look_at[0]:+.2f} Y={look_at[1]:+.2f}m (BS: {len(bs)} keys)"
                )

            # Standard Generic JSON
            return ARFaceFrame(
                timestamp=float(d.get("timestamp", 0.0)),
                head_pos=np.array(d.get("head_pos", [0, 0, 0.45]), dtype=np.float32),
                head_rot=np.array(d.get("head_rot", [0, 0, 0, 1]), dtype=np.float32),
                left_gaze=np.array(d.get("left_gaze", [0, 0, -1]), dtype=np.float32),
                right_gaze=np.array(d.get("right_gaze", [0, 0, -1]), dtype=np.float32),
                look_at_point=np.array(d.get("look_at", [0, 0, 0]), dtype=np.float32),
                blink_left=float(d.get("blink_left", 0.0)),
                blink_right=float(d.get("blink_right", 0.0)),
                raw_packet_debug="Generic JSON stream",
                raw_gaze_debug="Generic JSON"
            )
        except Exception:
            pass

    # 3. Text / iFacialMocap / FaceCap
    if "=head#" in text or "head#" in text or "eyeleft#" in text.lower() or "blendshape#" in text.lower() or "|" in text:
        frame = parse_ifacialmocap_packet(text)
        if frame is not None:
            return frame

    return None


def pack_binary_frame(frame: ARFaceFrame) -> bytes:
    return struct.pack(
        BINARY_FORMAT,
        MAGIC_HEADER,
        frame.timestamp,
        frame.head_pos[0], frame.head_pos[1], frame.head_pos[2],
        frame.head_rot[0], frame.head_rot[1], frame.head_rot[2], frame.head_rot[3],
        frame.left_gaze[0], frame.left_gaze[1], frame.left_gaze[2],
        frame.right_gaze[0], frame.right_gaze[1], frame.right_gaze[2],
        frame.look_at_point[0], frame.look_at_point[1], frame.look_at_point[2],
        frame.blink_left,
        frame.blink_right
    )
