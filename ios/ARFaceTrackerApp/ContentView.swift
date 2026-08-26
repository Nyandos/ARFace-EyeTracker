import SwiftUI

/// Hallmark Modern-Minimal Precision SwiftUI Interface for ARFace-Eyetracker
struct ContentView: View {
    @StateObject private var sender = ARFaceDataSender()

    @AppStorage("target_pc_ip") private var targetIP: String = "192.168.1.100"
    @AppStorage("target_pc_port") private var targetPort: String = "5005"
    @State private var selectedMode: StreamMode = .binary
    @State private var isEcoMode: Bool = false
    @State private var showPhotoPicker: Bool = false
    @State private var showSensorLab: Bool = false

    var body: some View {
        ZStack {
            // Dark Matte Canvas (#0B0F17)
            Color(red: 11/255, green: 15/255, blue: 23/255)
                .ignoresSafeArea()

            if isEcoMode && sender.isStreaming {
                // Eco Blackout Mode (Ultra-low heat / power)
                VStack(spacing: 24) {
                    Spacer()

                    ZStack {
                        Circle()
                            .fill(Color(red: 16/255, green: 185/255, blue: 129/255).opacity(0.15))
                            .frame(width: 80, height: 80)
                        Image(systemName: "moon.fill")
                            .font(.system(size: 32))
                            .foregroundColor(Color(red: 16/255, green: 185/255, blue: 129/255))
                    }

                    VStack(spacing: 6) {
                        Text("ECO STREAM ACTIVE")
                            .font(.system(size: 13, weight: .bold, design: .monospaced))
                            .foregroundColor(Color(red: 249/255, green: 250/255, blue: 251/255))
                            .tracking(1.2)

                        Text("\(sender.currentFPS, specifier: "%.1f") FPS // Zero-Render Mode")
                            .font(.system(size: 12, weight: .medium, design: .monospaced))
                            .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))

                        Text("Format: \(sender.streamMode.rawValue)")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundColor(Color(red: 107/255, green: 114/255, blue: 128/255))
                    }

                    Spacer()

                    Button(action: { isEcoMode = false }) {
                        Text("WAKE DISPLAY")
                            .font(.system(size: 11, weight: .bold, design: .monospaced))
                            .tracking(1.0)
                            .padding(.horizontal, 24)
                            .padding(.vertical, 12)
                            .background(Color(red: 31/255, green: 41/255, blue: 55/255))
                            .cornerRadius(8)
                            .foregroundColor(Color(red: 243/255, green: 244/255, blue: 246/255))
                    }
                    .padding(.bottom, 36)
                }
            } else {
                // Precision Telemetry & Config UI
                ScrollView {
                    VStack(spacing: 18) {
                        // Header Bar
                        HStack {
                            VStack(alignment: .leading, spacing: 3) {
                                Text("ARFACE // STREAMER")
                                    .font(.system(size: 16, weight: .black, design: .default))
                                    .foregroundColor(Color(red: 249/255, green: 250/255, blue: 251/255))
                                    .tracking(1.0)

                                Text("TrueDepth 3D Spatial Raw Ingest")
                                    .font(.system(size: 11, weight: .medium))
                                    .foregroundColor(Color(red: 107/255, green: 114/255, blue: 128/255))
                            }
                            Spacer()

                            // Status Pill
                            HStack(spacing: 6) {
                                Circle()
                                    .fill(sender.isStreaming ? (sender.isFaceTracked ? Color(red: 16/255, green: 185/255, blue: 129/255) : Color(red: 245/255, green: 158/255, blue: 11/255)) : Color(red: 239/255, green: 68/255, blue: 68/255))
                                    .frame(width: 8, height: 8)
                                Text(sender.isStreaming ? (sender.isFaceTracked ? "ACTIVE" : "LOCKING") : "OFFLINE")
                                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                                    .foregroundColor(Color(red: 209/255, green: 213/255, blue: 219/255))
                            }
                            .padding(.horizontal, 10)
                            .padding(.vertical, 5)
                            .background(Color(red: 17/255, green: 24/255, blue: 39/255))
                            .cornerRadius(12)
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(red: 31/255, green: 41/255, blue: 55/255), lineWidth: 1))
                        }
                        .padding(.top, 16)

                        // 1. Connection Ingest Card
                        VStack(alignment: .leading, spacing: 12) {
                            Text("INGEST ENDPOINT (UDP)")
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                                .tracking(0.8)

                            VStack(spacing: 8) {
                                HStack {
                                    Text("IP")
                                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                                        .foregroundColor(Color(red: 107/255, green: 114/255, blue: 128/255))
                                        .frame(width: 44, alignment: .leading)
                                    TextField("192.168.1.100", text: $targetIP)
                                        .font(.system(size: 13, design: .monospaced))
                                        .padding(8)
                                        .background(Color(red: 22/255, green: 31/255, blue: 48/255))
                                        .cornerRadius(6)
                                        .foregroundColor(.white)
                                        .disabled(sender.isStreaming)
                                }

                                HStack {
                                    Text("PORT")
                                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                                        .foregroundColor(Color(red: 107/255, green: 114/255, blue: 128/255))
                                        .frame(width: 44, alignment: .leading)
                                    TextField("5005", text: $targetPort)
                                        .font(.system(size: 13, design: .monospaced))
                                        .padding(8)
                                        .background(Color(red: 22/255, green: 31/255, blue: 48/255))
                                        .cornerRadius(6)
                                        .foregroundColor(.white)
                                        .disabled(sender.isStreaming)
                                }
                            }
                        }
                        .padding(14)
                        .background(Color(red: 17/255, green: 24/255, blue: 39/255))
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(red: 31/255, green: 41/255, blue: 55/255), lineWidth: 1))

                        // 2. Stream Mode Card
                        VStack(alignment: .leading, spacing: 10) {
                            Text("STREAM PROTOCOL MODE")
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                                .tracking(0.8)

                            Picker("Protocol", selection: $selectedMode) {
                                ForEach(StreamMode.allCases) { mode in
                                    Text(mode.rawValue).tag(mode)
                                }
                            }
                            .pickerStyle(SegmentedPickerStyle())
                            .disabled(sender.isStreaming)

                            HStack {
                                Text(selectedMode == .rawJSON ? "全52種BlendShapes・4x4行列・両目姿勢を完全送信" : "84バイト固定バイナリで超低遅延・高レート送信")
                                    .font(.system(size: 10))
                                    .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                                Spacer()
                            }
                        }
                        .padding(14)
                        .background(Color(red: 17/255, green: 24/255, blue: 39/255))
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(red: 31/255, green: 41/255, blue: 55/255), lineWidth: 1))

                        // 3. Telemetry Metrics Card
                        VStack(alignment: .leading, spacing: 12) {
                            Text("TELEMETRY METRICS")
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .foregroundColor(Color(red: 156/255, green: 163/255, blue: 175/255))
                                .tracking(0.8)

                            HStack(spacing: 12) {
                                // Rate Box
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("OUTPUT RATE")
                                        .font(.system(size: 9, weight: .bold))
                                        .foregroundColor(Color(red: 107/255, green: 114/255, blue: 128/255))
                                    Text("\(sender.currentFPS, specifier: "%.1f") FPS")
                                        .font(.system(size: 18, weight: .bold, design: .monospaced))
                                        .foregroundColor(sender.isStreaming ? Color(red: 52/255, green: 211/255, blue: 153/255) : Color(red: 107/255, green: 114/255, blue: 128/255))
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(10)
                                .background(Color(red: 22/255, green: 31/255, blue: 48/255))
                                .cornerRadius(6)

                                // Packet Size
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("PACKET SIZE")
                                        .font(.system(size: 9, weight: .bold))
                                        .foregroundColor(Color(red: 107/255, green: 114/255, blue: 128/255))
                                    Text(sender.isStreaming ? "\(sender.lastPacketSizeBytes) B" : "--")
                                        .font(.system(size: 16, weight: .bold, design: .monospaced))
                                        .foregroundColor(Color(red: 243/255, green: 244/255, blue: 246/255))
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(10)
                                .background(Color(red: 22/255, green: 31/255, blue: 48/255))
                                .cornerRadius(6)
                            }
                        }
                        .padding(14)
                        .background(Color(red: 17/255, green: 24/255, blue: 39/255))
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(red: 31/255, green: 41/255, blue: 55/255), lineWidth: 1))

                        // 4. Actions
                        VStack(spacing: 10) {
                            Button(action: toggleStreaming) {
                                HStack(spacing: 8) {
                                    Image(systemName: sender.isStreaming ? "stop.fill" : "bolt.fill")
                                    Text(sender.isStreaming ? "TERMINATE STREAM" : "START UDP STREAM")
                                }
                                .font(.system(size: 13, weight: .bold, design: .monospaced))
                                .tracking(0.8)
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 13)
                                .background(sender.isStreaming ? Color(red: 220/255, green: 38/255, blue: 38/255) : Color(red: 2/255, green: 132/255, blue: 199/255))
                                .cornerRadius(6)
                            }

                            if sender.isStreaming {
                                Button(action: { isEcoMode = true }) {
                                    HStack(spacing: 6) {
                                        Image(systemName: "moon.fill")
                                        Text("ENGAGE ECO MODE (BLACKOUT)")
                                    }
                                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                                    .tracking(0.5)
                                    .foregroundColor(Color(red: 52/255, green: 211/255, blue: 153/255))
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 10)
                                    .background(Color(red: 16/255, green: 185/255, blue: 129/255).opacity(0.12))
                                    .cornerRadius(6)
                                }
                            }

                            // 5. 3D Spatial Alignment Photo Capture Button
                            Button(action: { showPhotoPicker = true }) {
                                HStack(spacing: 6) {
                                    Image(systemName: "camera.viewfinder")
                                    Text("📷 CAPTURE MONITOR PHOTO (3D測定)")
                                }
                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                .tracking(0.5)
                                .foregroundColor(Color(red: 199/255, green: 210/255, blue: 254/255))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color(red: 30/255, green: 27/255, blue: 75/255))
                                .cornerRadius(6)
                                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color(red: 99/255, green: 102/255, blue: 241/255), lineWidth: 1))
                            }

                            // 6. Sensor Lab (Monitor Angle & Levels)
                            Button(action: { showSensorLab = true }) {
                                HStack(spacing: 6) {
                                    Image(systemName: "compass.drawing")
                                    Text("🧭 SENSOR LAB (モニター角度・水準器)")
                                }
                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                .tracking(0.5)
                                .foregroundColor(Color(red: 254/255, green: 240/255, blue: 138/255))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(Color(red: 66/255, green: 32/255, blue: 6/255).opacity(0.6))
                                .cornerRadius(6)
                                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color(red: 234/255, green: 179/255, blue: 8/255), lineWidth: 1))
                            }
                        }

                        Spacer()
                    }
                    .padding(.horizontal, 18)
                }
            }
        }
        .sheet(isPresented: $showPhotoPicker) {
            ImagePickerView(sourceType: .camera) { image in
                uploadPhotoToPC(image: image)
            }
        }
        .sheet(isPresented: $showSensorLab) {
            SensorLabView(targetIP: targetIP)
        }
    }

    private func toggleStreaming() {
        if sender.isStreaming {
            sender.stopTracking()
        } else {
            let port = UInt16(targetPort) ?? 5005
            sender.startTracking(targetIP: targetIP, targetPort: port, mode: selectedMode)
        }
    }

    private func uploadPhotoToPC(image: UIImage) {
        guard let jpegData = image.jpegData(compressionQuality: 0.82),
              let url = URL(string: "http://\(targetIP):5006/upload_photo") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("image/jpeg", forHTTPHeaderField: "Content-Type")
        request.httpBody = jpegData
        URLSession.shared.dataTask(with: request) { _, _, error in
            if let error = error {
                print("[iOS] Photo upload failed: \(error)")
            } else {
                print("[iOS] Monitor photo successfully uploaded to PC!")
            }
        }.resume()
    }
}

/// Simple UIKit Camera / Photo Picker Sheet for SwiftUI
struct ImagePickerView: UIViewControllerRepresentable {
    var sourceType: UIImagePickerController.SourceType = .camera
    var onImagePicked: (UIImage) -> Void
    @Environment(\.presentationMode) private var presentationMode

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        if UIImagePickerController.isSourceTypeAvailable(sourceType) {
            picker.sourceType = sourceType
        } else {
            picker.sourceType = .photoLibrary
        }
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: ImagePickerView

        init(_ parent: ImagePickerView) {
            self.parent = parent
        }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey : Any]) {
            if let image = info[.originalImage] as? UIImage {
                parent.onImagePicked(image)
            }
            parent.presentationMode.wrappedValue.dismiss()
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.presentationMode.wrappedValue.dismiss()
        }
    }
}
