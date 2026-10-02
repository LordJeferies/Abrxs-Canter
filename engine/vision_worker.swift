import Foundation
import ImageIO
import CoreGraphics
import CoreVideo
import Vision

// Análisis local muestreado. No genera narración semántica de las acciones.
func emit(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
       let line = String(data: data, encoding: .utf8) {
        print("ABRXS_VISION:" + line)
        fflush(stdout)
    }
}
func box(_ rect: CGRect) -> [String: Double] {
    ["x": Double(rect.minX), "y": Double(1 - rect.maxY), "width": Double(rect.width), "height": Double(rect.height)]
}
func pixelBuffer(_ image: CGImage) throws -> CVPixelBuffer {
    var result: CVPixelBuffer?
    let attributes = [kCVPixelBufferCGImageCompatibilityKey: true, kCVPixelBufferCGBitmapContextCompatibilityKey: true] as CFDictionary
    let status = CVPixelBufferCreate(kCFAllocatorDefault, image.width, image.height, kCVPixelFormatType_32BGRA, attributes, &result)
    guard status == kCVReturnSuccess, let buffer = result else {
        throw NSError(domain: "Abrxs", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "No se pudo crear el buffer local para Vision"])
    }
    CVPixelBufferLockBaseAddress(buffer, [])
    defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
    guard let context = CGContext(data: CVPixelBufferGetBaseAddress(buffer), width: image.width, height: image.height,
        bitsPerComponent: 8, bytesPerRow: CVPixelBufferGetBytesPerRow(buffer), space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue) else {
        throw NSError(domain: "Abrxs", code: 4, userInfo: [NSLocalizedDescriptionKey: "No se pudo preparar el fotograma para Vision"])
    }
    context.draw(image, in: CGRect(x: 0, y: 0, width: image.width, height: image.height))
    return buffer
}
do {
    guard CommandLine.arguments.count == 2,
          let data = FileHandle.standardInput.readDataToEndOfFile() as Data?,
          let req = try JSONSerialization.jsonObject(with: data) as? [String: Any],
          let frames = req["frames"] as? [[String: Any]], !frames.isEmpty, frames.count <= 600 else {
        throw NSError(domain: "Abrxs", code: 1, userInfo: [NSLocalizedDescriptionKey: "Petición inválida"])
    }
    let mode = req["mode"] as? String ?? "analysis"
    let sequence = VNSequenceRequestHandler()
    var tracked: VNDetectedObjectObservation?
    if mode == "object", let rect = req["rect"] as? [Double], rect.count == 4 {
        tracked = VNDetectedObjectObservation(boundingBox: CGRect(x: rect[0], y: 1 - rect[1] - rect[3], width: rect[2], height: rect[3]))
    }
    for frame in frames {
        try autoreleasepool {
            guard let path = frame["path"] as? String, let time = frame["time"] as? Double,
                  let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
                  let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
                throw NSError(domain: "Abrxs", code: 3, userInfo: [NSLocalizedDescriptionKey: "Fotograma inválido"])
            }
            let faces = VNDetectFaceRectanglesRequest()
            let bodies = VNDetectHumanRectanglesRequest()
            let text = VNRecognizeTextRequest()
            text.recognitionLevel = .fast
            text.usesLanguageCorrection = false
            text.recognitionLanguages = ["en-US", "es-ES"]
            faces.usesCPUOnly = true
            bodies.usesCPUOnly = true
            text.usesCPUOnly = true
            let pixels = try pixelBuffer(image)
            let handler = VNImageRequestHandler(cvPixelBuffer: pixels, options: [:])
            try handler.perform([faces, bodies, text])
            var sample: [String: Any] = ["time": time,
                "faces": (faces.results ?? []).map { box($0.boundingBox) },
                "bodies": (bodies.results ?? []).map { box($0.boundingBox) },
                "text": (text.results ?? []).prefix(30).compactMap { observation -> [String: Any]? in
                    guard let candidate = observation.topCandidates(1).first else { return nil }
                    return ["text": candidate.string, "confidence": candidate.confidence, "box": box(observation.boundingBox)]
                }]
            if mode != "analysis" {
                if let previous = tracked {
                    let request = VNTrackObjectRequest(detectedObjectObservation: previous)
                    request.trackingLevel = .accurate
                    request.usesCPUOnly = true
                    try sequence.perform([request], on: pixels)
                    let observation = request.results?.first as? VNDetectedObjectObservation
                    tracked = observation.flatMap { $0.confidence >= 0.45 ? $0 : nil }
                }
                // Face/body puede recuperar detección; object nunca cambia a otro objeto.
                if tracked == nil && mode != "object" {
                    let detected: VNDetectedObjectObservation? = mode == "face" ?
                        (faces.results ?? []).max(by: { $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height }) :
                        (bodies.results ?? []).max(by: { $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height })
                    tracked = detected
                }
                if let target = tracked {
                    sample["target"] = box(target.boundingBox)
                    sample["confidence"] = target.confidence
                } else { sample["lost"] = true }
            }
            emit(sample)
        }
    }
} catch {
    FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
    exit(1)
}
