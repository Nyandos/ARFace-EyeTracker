import Foundation
import ARKit
import Network
import simd

/// Supported streaming modes
enum StreamMode: String, CaseIterable, Identifiable {
    case rawJSON = "Raw JSON (全生データ)"
    case binary = "Fast Binary (ARF1 84B)"

    var id: String { self.rawValue }
}

/// High-performance UDP sender and TrueDepth Face Tracking Manager
class ARFaceDataSender: NSObject, ObservableObject, ARSessionDelegate {
    @Published var isStreaming: Bool = false
    @Published var currentFPS: Double = 0.0
    @Published var trackingStateText: String = "Ready"
    @Published var isFaceTracked: Bool = false
    @Published var streamMode: StreamMode = .rawJSON
    @Published var lastPacketSizeBytes: Int = 0

    private var session: ARSession?
    private var connection: NWConnection?
    private var host: NWEndpoint.Host = "192.168.1.100"
    private var port: NWEndpoint.Port = 5005

    // FPS Calculation
    private var frameCount: Int = 0
    private var lastFpsCalcTime: TimeInterval = 0

    // Magic Header: "ARF1"
    private let magicHeader: [UInt8] = [0x41, 0x52, 0x46, 0x31]

    override init() {
        super.init()
    }

    func startTracking(targetIP: String, targetPort: UInt16, mode: StreamMode = .rawJSON) {
        guard ARFaceTrackingConfiguration.isSupported else {
            trackingStateText = "FaceID (TrueDepth) Not Supported"
            return
        }

        self.streamMode = mode
        self.host = NWEndpoint.Host(targetIP)
        if let p = NWEndpoint.Port(rawValue: targetPort) {
            self.port = p
        }

        // Setup UDP Connection
        let params = NWParameters.udp
        params.allowLocalEndpointReuse = true
        self.connection = NWConnection(host: self.host, port: self.port, using: params)
        self.connection?.stateUpdateHandler = { state in
            switch state {
            case .ready:
                print("[Network] UDP connection ready to \(targetIP):\(targetPort)")
            case .failed(let error):
                print("[Network] UDP connection failed: \(error)")
            default:
                break
            }
        }
        self.connection?.start(queue: .global(qos: .userInteractive))

        // Setup ARKit Session
        let config = ARFaceTrackingConfiguration()
        config.isLightEstimationEnabled = false
        if #available(iOS 13.0, *) {
            config.maximumNumberOfTrackedFaces = 1
        }

        self.session = ARSession()
        self.session?.delegate = self
        self.session?.run(config, options: [.resetTracking, .removeExistingAnchors])

        self.isStreaming = true
        self.trackingStateText = "Tracking Active"
        self.lastFpsCalcTime = ProcessInfo.processInfo.systemUptime
    }

    func stopTracking() {
        self.session?.pause()
        self.session = nil
        self.connection?.cancel()
        self.connection = nil
        self.isStreaming = false
        self.isFaceTracked = false
        self.trackingStateText = "Stopped"
        self.currentFPS = 0.0
        self.lastPacketSizeBytes = 0
    }

    // MARK: - ARSessionDelegate
    func session(_ session: ARSession, didUpdate anchors: [ARAnchor]) {
        guard isStreaming else { return }

        for anchor in anchors {
            if let faceAnchor = anchor as? ARFaceAnchor, faceAnchor.isTracked {
                DispatchQueue.main.async {
                    self.isFaceTracked = true
                }
                
                switch self.streamMode {
                case .rawJSON:
                    sendRawJSONData(faceAnchor: faceAnchor)
                case .binary:
                    sendBinaryFaceData(faceAnchor: faceAnchor)
                }
                
                updateFpsCounter()
                return
            }
        }

        DispatchQueue.main.async {
            self.isFaceTracked = false
        }
    }

    func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
        DispatchQueue.main.async {
            switch camera.trackingState {
            case .normal:
                self.trackingStateText = "Normal"
            case .limited(let reason):
                self.trackingStateText = "Limited: \(reason)"
            case .notAvailable:
                self.trackingStateText = "Not Available"
            }
        }
    }

    // MARK: - Helper Methods
    private func extractRotationQuat(_ m: simd_float4x4) -> simd_quatf {
        let rot3x3 = simd_float3x3(
            simd_float3(m.columns.0.x, m.columns.0.y, m.columns.0.z),
            simd_float3(m.columns.1.x, m.columns.1.y, m.columns.1.z),
            simd_float3(m.columns.2.x, m.columns.2.y, m.columns.2.z)
        )
        return simd_quatf(rot3x3)
    }

    // MARK: - Raw JSON Stream (All 52 BlendShapes + Matrices + Vectors)
    private func sendRawJSONData(faceAnchor: ARFaceAnchor) {
        guard let connection = self.connection else { return }

        let now = Date().timeIntervalSince1970
        let transform = faceAnchor.transform
        let headPos = simd_float3(transform.columns.3.x, transform.columns.3.y, transform.columns.3.z)
        let headRot = extractRotationQuat(transform)

        let leftLook = faceAnchor.leftEyeTransform.columns.2
        let rightLook = faceAnchor.rightEyeTransform.columns.2
        let leftGaze = simd_float3(leftLook.x, leftLook.y, leftLook.z)
        let rightGaze = simd_float3(rightLook.x, rightLook.y, rightLook.z)
        let lookAtPoint = faceAnchor.lookAtPoint

        // Extract all 52 BlendShapes rounded to 4 decimals for compact MTU-friendly UDP
        var blendShapesDict: [String: Double] = [:]
        blendShapesDict.reserveCapacity(faceAnchor.blendShapes.count)
        for (key, val) in faceAnchor.blendShapes {
            let rounded = (val.doubleValue * 10000.0).rounded() / 10000.0
            blendShapesDict[key.rawValue] = rounded
        }

        // Helper for rounding simd_float3
        func round3(_ v: simd_float3) -> [Double] {
            return [
                (Double(v.x) * 10000.0).rounded() / 10000.0,
                (Double(v.y) * 10000.0).rounded() / 10000.0,
                (Double(v.z) * 10000.0).rounded() / 10000.0
            ]
        }

        // Helper for 4x4 matrix flattening
        func matrixToArray(_ m: simd_float4x4) -> [Double] {
            return [
                Double(m.columns.0.x), Double(m.columns.0.y), Double(m.columns.0.z), Double(m.columns.0.w),
                Double(m.columns.1.x), Double(m.columns.1.y), Double(m.columns.1.z), Double(m.columns.1.w),
                Double(m.columns.2.x), Double(m.columns.2.y), Double(m.columns.2.z), Double(m.columns.2.w),
                Double(m.columns.3.x), Double(m.columns.3.y), Double(m.columns.3.z), Double(m.columns.3.w)
            ].map { ($0 * 10000.0).rounded() / 10000.0 }
        }

        let payload: [String: Any] = [
            "timestamp": now,
            "head": [
                "position": round3(headPos),
                "rotation": [
                    (Double(headRot.vector.x) * 10000.0).rounded() / 10000.0,
                    (Double(headRot.vector.y) * 10000.0).rounded() / 10000.0,
                    (Double(headRot.vector.z) * 10000.0).rounded() / 10000.0,
                    (Double(headRot.vector.w) * 10000.0).rounded() / 10000.0
                ],
                "matrix": matrixToArray(transform)
            ],
            "leftEye": [
                "lookDirection": round3(leftGaze),
                "matrix": matrixToArray(faceAnchor.leftEyeTransform)
            ],
            "rightEye": [
                "lookDirection": round3(rightGaze),
                "matrix": matrixToArray(faceAnchor.rightEyeTransform)
            ],
            "lookAtPoint": round3(lookAtPoint),
            "blendShapes": blendShapesDict
        ]

        if let jsonData = try? JSONSerialization.data(withJSONObject: payload, options: []) {
            connection.send(content: jsonData, completion: .idempotent)
            DispatchQueue.main.async {
                self.lastPacketSizeBytes = jsonData.count
            }
        }
    }

    // MARK: - Binary Serialization and UDP Send (Fast 84-byte ARF1)
    private func sendBinaryFaceData(faceAnchor: ARFaceAnchor) {
        guard let connection = self.connection else { return }

        let now = Date().timeIntervalSince1970
        let transform = faceAnchor.transform
        let headPos = simd_float3(transform.columns.3.x, transform.columns.3.y, transform.columns.3.z)
        let headRot = extractRotationQuat(transform)

        let leftLook = faceAnchor.leftEyeTransform.columns.2
        let rightLook = faceAnchor.rightEyeTransform.columns.2
        let leftGaze = simd_float3(leftLook.x, leftLook.y, leftLook.z)
        let rightGaze = simd_float3(rightLook.x, rightLook.y, rightLook.z)
        let lookAtPoint = faceAnchor.lookAtPoint

        let blinkLeft = Float(truncating: faceAnchor.blendShapes[.eyeBlinkLeft] ?? 0.0)
        let blinkRight = Float(truncating: faceAnchor.blendShapes[.eyeBlinkRight] ?? 0.0)

        // Build 84-byte binary packet: Big-Endian
        var data = Data()
        data.append(contentsOf: magicHeader) // 4 bytes

        // timestamp: Double (8 bytes)
        appendDoubleBE(&data, now)

        // head_pos: 3x Float (12 bytes)
        appendFloatBE(&data, headPos.x)
        appendFloatBE(&data, headPos.y)
        appendFloatBE(&data, headPos.z)

        // head_rot: 4x Float (16 bytes) [qx, qy, qz, qw]
        appendFloatBE(&data, headRot.vector.x)
        appendFloatBE(&data, headRot.vector.y)
        appendFloatBE(&data, headRot.vector.z)
        appendFloatBE(&data, headRot.vector.w)

        // left_gaze: 3x Float (12 bytes)
        appendFloatBE(&data, leftGaze.x)
        appendFloatBE(&data, leftGaze.y)
        appendFloatBE(&data, leftGaze.z)

        // right_gaze: 3x Float (12 bytes)
        appendFloatBE(&data, rightGaze.x)
        appendFloatBE(&data, rightGaze.y)
        appendFloatBE(&data, rightGaze.z)

        // look_at_point: 3x Float (12 bytes)
        appendFloatBE(&data, lookAtPoint.x)
        appendFloatBE(&data, lookAtPoint.y)
        appendFloatBE(&data, lookAtPoint.z)

        // blinks: 2x Float (8 bytes)
        appendFloatBE(&data, blinkLeft)
        appendFloatBE(&data, blinkRight)

        connection.send(content: data, completion: .idempotent)
        DispatchQueue.main.async {
            self.lastPacketSizeBytes = data.count
        }
    }

    private func appendFloatBE(_ data: inout Data, _ value: Float) {
        var be = value.bitPattern.bigEndian
        withUnsafeBytes(of: &be) { buffer in
            data.append(contentsOf: buffer)
        }
    }

    private func appendDoubleBE(_ data: inout Data, _ value: Double) {
        var be = value.bitPattern.bigEndian
        withUnsafeBytes(of: &be) { buffer in
            data.append(contentsOf: buffer)
        }
    }

    private func updateFpsCounter() {
        frameCount += 1
        let now = ProcessInfo.processInfo.systemUptime
        let elapsed = now - lastFpsCalcTime
        if elapsed >= 0.5 {
            let fps = Double(frameCount) / elapsed
            frameCount = 0
            lastFpsCalcTime = now
            DispatchQueue.main.async {
                self.currentFPS = fps
            }
        }
    }
}
