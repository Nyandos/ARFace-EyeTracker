import SwiftUI
import CoreMotion
import ARKit

/// Hallmark Precision Space: SENSOR LAB & Spatial Alignment Toolbox (v5.0)
struct SensorLabView: View {
    let targetIP: String
    @Environment(\.presentationMode) var presentationMode

    @StateObject private var motionMgr = PrecisionMotionManager()

    // Calibration Steps
    @State private var step: Int = 1
    @State private var lockedMonitorPitch: Double? = nil
    @State private var lockedMonitorBackTilt: Double? = nil
    @State private var lockedMonitorRoll: Double? = nil
    @State private var lockedPhonePitch: Double? = nil
    @State private var lockedPhoneRoll: Double? = nil
    @State private var uploadStatus: String? = nil

    // 3-Second Timer
    @State private var countdown: Int = 0
    @State private var timer: Timer? = nil

    var body: some View {
        ZStack {
            Color(red: 11/255, green: 15/255, blue: 23/255).ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("SENSOR LAB // SPATIAL METRICS")
                            .font(.system(size: 13, weight: .black, design: .monospaced))
                            .foregroundColor(.white)
                            .tracking(1.0)
                        Text("Precision Inclinometer & Distance Radar")
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                    }
                    Spacer()
                    Button(action: { presentationMode.wrappedValue.dismiss() }) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 22))
                            .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                    }
                }
                .padding(.horizontal, 18)
                .padding(.top, 16)
                .padding(.bottom, 12)

                Divider().background(Color(red: 31/255, green: 41/255, blue: 55/255))

                ScrollView {
                    VStack(spacing: 16) {
                        // 1. Monitor Angle Inclinometer Tool
                        monitorAngleCard

                        // 2. Dual-Axis Bubble Level
                        bubbleLevelCard

                        // 3. Live IMU Raw Angles
                        liveMetricsCard

                        Spacer(minLength: 24)
                    }
                    .padding(18)
                }
            }
        }
        .onAppear {
            motionMgr.start()
        }
        .onDisappear {
            motionMgr.stop()
            timer?.invalidate()
        }
    }

    // -------------------------------------------------------------
    // Card 1: Monitor Angle Inclinometer Step-by-Step
    // -------------------------------------------------------------
    private var monitorAngleCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "display.and.arrow.down")
                    .foregroundColor(Color(red: 56/255, green: 189/255, blue: 248/255))
                Text("📐 モニター角度キャリブレータ")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.white)
                Spacer()
                Text("STEP \(step) / 2")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundColor(Color(red: 56/255, green: 189/255, blue: 248/255))
            }

            if step == 1 {
                VStack(alignment: .leading, spacing: 10) {
                    Text("ボタンを押したら、3秒以内にiPhoneの画面をPCモニターにぴったり密着させてください。")
                        .font(.system(size: 12))
                        .foregroundColor(Color(red: 229/255, green: 231/255, blue: 235/255))

                    Text("密着時に画面が見えなくても、3秒後に振動（ハプティクス）で自動ロックされます。")
                        .font(.system(size: 11))
                        .foregroundColor(Color(red: 56/255, green: 189/255, blue: 248/255))

                    HStack {
                        Text("現在のリアルタイム傾斜:")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                        Spacer()
                        Text("\(motionMgr.pitch, specifier: "%.2f")°")
                            .font(.system(size: 18, weight: .bold, design: .monospaced))
                            .foregroundColor(Color(red: 52/255, green: 211/255, blue: 153/255))
                    }
                    .padding(10)
                    .background(Color(red: 22/255, green: 31/255, blue: 48/255))
                    .cornerRadius(6)

                    if countdown > 0 {
                        // Countdown Active Display
                        VStack(spacing: 4) {
                            Text("画面をモニターに当ててください...")
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(Color(red: 251/255, green: 191/255, blue: 36/255))
                            Text("\(countdown)")
                                .font(.system(size: 36, weight: .black, design: .monospaced))
                                .foregroundColor(Color(red: 251/255, green: 191/255, blue: 36/255))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(Color(red: 251/255, green: 191/255, blue: 36/255).opacity(0.15))
                        .cornerRadius(6)
                    } else {
                        // Trigger Button
                        Button(action: startCountdownMeasurement) {
                            HStack(spacing: 8) {
                                Image(systemName: "timer")
                                Text("⏳ 3秒タイマーでモニター密着測定を開始")
                            }
                            .font(.system(size: 13, weight: .bold))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Color(red: 2/255, green: 132/255, blue: 199/255))
                            .cornerRadius(6)
                        }
                    }
                }
            } else {
                VStack(alignment: .leading, spacing: 10) {
                    Text("iPhoneを机のスタンド（使用位置）に置いてください。")
                        .font(.system(size: 12))
                        .foregroundColor(Color(red: 229/255, green: 231/255, blue: 235/255))

                    if let bTilt = lockedMonitorBackTilt {
                        HStack {
                            Text("測定済みモニター後傾角:")
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                            Spacer()
                            Text("\(bTilt >= 0 ? "+" : "")\(bTilt, specifier: "%.2f")° (垂直から)")
                                .font(.system(size: 13, weight: .bold, design: .monospaced))
                                .foregroundColor(Color(red: 56/255, green: 189/255, blue: 248/255))
                        }
                        .padding(8)
                        .background(Color(red: 22/255, green: 31/255, blue: 48/255))
                        .cornerRadius(6)
                    }

                    HStack {
                        Text("スタンドでのiPhone仰角:")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                        Spacer()
                        let phoneTilt = max(0.0, 90.0 - motionMgr.pitch)
                        Text("\(phoneTilt, specifier: "%.2f")°")
                            .font(.system(size: 18, weight: .bold, design: .monospaced))
                            .foregroundColor(Color(red: 52/255, green: 211/255, blue: 153/255))
                    }
                    .padding(10)
                    .background(Color(red: 22/255, green: 31/255, blue: 48/255))
                    .cornerRadius(6)

                    HStack(spacing: 10) {
                        Button(action: { step = 1 }) {
                            Text("再測定")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                                .frame(width: 80)
                                .padding(.vertical, 11)
                                .background(Color(red: 31/255, green: 41/255, blue: 55/255))
                                .cornerRadius(6)
                        }

                        Button(action: uploadCalibrationToPC) {
                            HStack {
                                Image(systemName: "arrow.up.circle.fill")
                                Text("📡 PCへ角度データを送信")
                            }
                            .font(.system(size: 12, weight: .bold))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 11)
                            .background(Color(red: 5/255, green: 150/255, blue: 105/255))
                            .cornerRadius(6)
                        }
                    }

                    if let status = uploadStatus {
                        Text(status)
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .foregroundColor(Color(red: 52/255, green: 211/255, blue: 153/255))
                    }
                }
            }
        }
        .padding(14)
        .background(Color(red: 17/255, green: 24/255, blue: 39/255))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(red: 31/255, green: 41/255, blue: 55/255), lineWidth: 1))
    }

    // -------------------------------------------------------------
    // Card 2: Precision 2-Axis Bubble Level
    // -------------------------------------------------------------
    private var bubbleLevelCard: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "circle.circle")
                    .foregroundColor(Color(red: 16/255, green: 185/255, blue: 129/255))
                Text("📱 精密2軸水準器 (Bubble Level)")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.white)
                Spacer()
            }

            ZStack {
                Circle()
                    .stroke(Color(red: 31/255, green: 41/255, blue: 55/255), lineWidth: 2)
                    .frame(width: 130, height: 130)

                Circle()
                    .stroke(Color(red: 55/255, green: 65/255, blue: 81/255), lineWidth: 1)
                    .frame(width: 60, height: 60)

                // Crosshair
                Rectangle().fill(Color(red: 31/255, green: 41/255, blue: 55/255)).frame(width: 130, height: 1)
                Rectangle().fill(Color(red: 31/255, green: 41/255, blue: 55/255)).frame(width: 1, height: 130)

                // Dynamic Bubble
                let xOffset = CGFloat(max(-55.0, min(55.0, motionMgr.roll * 1.5)))
                let yOffset = CGFloat(max(-55.0, min(55.0, (motionMgr.pitch - 90.0) * 1.5)))

                Circle()
                    .fill(Color(red: 16/255, green: 185/255, blue: 129/255).opacity(0.8))
                    .frame(width: 22, height: 22)
                    .offset(x: xOffset, y: yOffset)
            }
            .frame(height: 140)

            HStack(spacing: 20) {
                VStack {
                    Text("PITCH (前後)")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(Color(red: 107/255, green: 114/255, blue: 128/255))
                    Text("\(motionMgr.pitch, specifier: "%.1f")°")
                        .font(.system(size: 15, weight: .bold, design: .monospaced))
                        .foregroundColor(.white)
                }

                VStack {
                    Text("ROLL (左右)")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(Color(red: 107/255, green: 114/255, blue: 128/255))
                    Text("\(motionMgr.roll, specifier: "%+.1f")°")
                        .font(.system(size: 15, weight: .bold, design: .monospaced))
                        .foregroundColor(.white)
                }
            }
        }
        .padding(14)
        .background(Color(red: 17/255, green: 24/255, blue: 39/255))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(red: 31/255, green: 41/255, blue: 55/255), lineWidth: 1))
    }

    // -------------------------------------------------------------
    // Card 3: Live Sensor Readings
    // -------------------------------------------------------------
    private var liveMetricsCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("IMU ACCELEROMETER & GRAVITY")
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                .tracking(0.8)

            HStack {
                Text("Gx: \(motionMgr.gravityX, specifier: "%+.3f")")
                Spacer()
                Text("Gy: \(motionMgr.gravityY, specifier: "%+.3f")")
                Spacer()
                Text("Gz: \(motionMgr.gravityZ, specifier: "%+.3f")")
            }
            .font(.system(size: 11, design: .monospaced))
            .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
        }
        .padding(14)
        .background(Color(red: 17/255, green: 24/255, blue: 39/255))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(red: 31/255, green: 41/255, blue: 55/255), lineWidth: 1))
    }

    // -------------------------------------------------------------
    // Actions
    // -------------------------------------------------------------
    private func startCountdownMeasurement() {
        countdown = 3
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { t in
            if countdown > 1 {
                countdown -= 1
            } else {
                t.invalidate()
                countdown = 0
                lockMonitorAngle()
            }
        }
    }

    private func lockMonitorAngle() {
        // Haptic feedback (Silent)
        let generator = UINotificationFeedbackGenerator()
        generator.prepare()
        generator.notificationOccurred(.success)

        lockedMonitorPitch = motionMgr.pitch
        lockedMonitorRoll = motionMgr.roll

        // Back tilt angle: When screen is pressed against monitor facing backwards,
        // if monitor is tilted backwards from vertical, top of phone leans away from user.
        // 90° = vertical upright. Less than 90° = tilted back.
        let backTilt = 90.0 - motionMgr.pitch
        lockedMonitorBackTilt = backTilt
        step = 2
    }

    private func uploadCalibrationToPC() {
        guard let bTilt = lockedMonitorBackTilt,
              let url = URL(string: "http://\(targetIP):5006/upload_sensor_data") else { return }

        // Upward tilt of iPhone on desk stand (0° = vertical upright, 28° = tilted up)
        let phoneUpwardTilt = max(0.0, 90.0 - motionMgr.pitch)
        // True physical intersection angle:
        // Phone upward tilt + Monitor backward tilt
        let relativeIntersect = phoneUpwardTilt + bTilt

        let payload: [String: Any] = [
            "monitor_pitch_deg": lockedMonitorPitch ?? 90.0,
            "monitor_back_tilt_deg": bTilt,
            "monitor_roll_deg": lockedMonitorRoll ?? 0.0,
            "phone_pitch_deg": motionMgr.pitch,
            "phone_upward_tilt_deg": phoneUpwardTilt,
            "phone_roll_deg": motionMgr.roll,
            "relative_angle_deg": relativeIntersect
        ]

        guard let jsonData = try? JSONSerialization.data(withJSONObject: payload) else { return }

        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = jsonData

        URLSession.shared.dataTask(with: req) { _, _, err in
            DispatchQueue.main.async {
                if let err = err {
                    self.uploadStatus = "送信エラー: \(err.localizedDescription)"
                } else {
                    self.uploadStatus = "✓ PCへ適用完了！ (相対交差角 \(String(format: "%.1f", relativeIntersect))°)"
                }
            }
        }.resume()
    }
}

/// Real-time 60Hz CoreMotion Attitude / Gravity Streamer
class PrecisionMotionManager: ObservableObject {
    private let motion = CMMotionManager()
    @Published var pitch: Double = 0.0
    @Published var roll: Double = 0.0
    @Published var gravityX: Double = 0.0
    @Published var gravityY: Double = 0.0
    @Published var gravityZ: Double = 0.0

    func start() {
        guard motion.isDeviceMotionAvailable else { return }
        motion.deviceMotionUpdateInterval = 1.0 / 30.0
        motion.startDeviceMotionUpdates(to: .main) { [weak self] data, _ in
            guard let self = self, let d = data else { return }
            self.gravityX = d.gravity.x
            self.gravityY = d.gravity.y
            self.gravityZ = d.gravity.z

            // Calculate upward angle relative to vertical earth gravity
            // 90° = standing vertically upright
            // 0° = lying flat horizontally
            let norm = sqrt(d.gravity.x * d.gravity.x + d.gravity.y * d.gravity.y + d.gravity.z * d.gravity.z)
            if norm > 1e-4 {
                let cosUp = max(-1.0, min(1.0, -d.gravity.y / norm))
                self.pitch = acos(cosUp) * 180.0 / .pi
            }

            self.roll = atan2(d.gravity.x, -d.gravity.y) * 180.0 / .pi
        }
    }

    func stop() {
        motion.stopDeviceMotionUpdates()
    }
}
