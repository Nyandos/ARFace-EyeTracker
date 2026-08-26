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
    @State private var lockedMonitorRoll: Double? = nil
    @State private var lockedPhonePitch: Double? = nil
    @State private var lockedPhoneRoll: Double? = nil
    @State private var uploadStatus: String? = nil

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
                VStack(alignment: .leading, spacing: 8) {
                    Text("iPhoneの画面をPCモニターにぴったり密着させてください。")
                        .font(.system(size: 12))
                        .foregroundColor(Color(red: 229/255, green: 231/255, blue: 235/255))

                    Text("モニター自体の設置傾斜角（チルト角）を0.01°単位で正確に測定します。")
                        .font(.system(size: 10))
                        .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))

                    HStack {
                        Text("現在のモニター傾斜:")
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

                    Button(action: lockMonitorAngle) {
                        HStack {
                            Image(systemName: "lock.fill")
                            Text("密着完了：モニター角度をロック")
                        }
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 11)
                        .background(Color(red: 2/255, green: 132/255, blue: 199/255))
                        .cornerRadius(6)
                    }
                }
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    Text("iPhoneを机のスタンド（使用位置）に置いてください。")
                        .font(.system(size: 12))
                        .foregroundColor(Color(red: 229/255, green: 231/255, blue: 235/255))

                    if let mPitch = lockedMonitorPitch {
                        HStack {
                            Text("ロック済みモニター角度:")
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                            Spacer()
                            Text("\(mPitch, specifier: "%.2f")°")
                                .font(.system(size: 14, weight: .bold, design: .monospaced))
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
                        Text("\(motionMgr.pitch, specifier: "%.2f")°")
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
    private func lockMonitorAngle() {
        lockedMonitorPitch = motionMgr.pitch
        lockedMonitorRoll = motionMgr.roll
        step = 2
    }

    private func uploadCalibrationToPC() {
        guard let mPitch = lockedMonitorPitch,
              let url = URL(string: "http://\(targetIP):5006/upload_sensor_data") else { return }

        let payload: [String: Any] = [
            "monitor_pitch_deg": mPitch,
            "monitor_roll_deg": lockedMonitorRoll ?? 0.0,
            "phone_pitch_deg": motionMgr.pitch,
            "phone_roll_deg": motionMgr.roll,
            "relative_angle_deg": abs(mPitch - motionMgr.pitch)
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
                    self.uploadStatus = "✓ PCへ適用完了！ (相対角 \(String(format: "%.1f", abs(mPitch - motionMgr.pitch)))°)"
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
