// Writes a tiny MP4: 64x64 grey frames for 0.5 s, optionally with silent AAC audio.
import AVFoundation
let args = CommandLine.arguments
let url = URL(fileURLWithPath: args[1]); let withAudio = args[2] == "1"; let withVideo = args.count < 4 || args[3] == "1"
try? FileManager.default.removeItem(at: url)
let w = try! AVAssetWriter(outputURL: url, fileType: .mp4)
var vin: AVAssetWriterInput? = nil; var ad: AVAssetWriterInputPixelBufferAdaptor? = nil
if withVideo {
  let v = AVAssetWriterInput(mediaType: .video, outputSettings: [AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: 64, AVVideoHeightKey: 64])
  v.expectsMediaDataInRealTime = false; w.add(v); vin = v
  ad = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: v, sourcePixelBufferAttributes: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA, kCVPixelBufferWidthKey as String: 64, kCVPixelBufferHeightKey as String: 64])
}
var ain: AVAssetWriterInput? = nil
if withAudio {
  let a = AVAssetWriterInput(mediaType: .audio, outputSettings: [AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 44100, AVNumberOfChannelsKey: 1, AVEncoderBitRateKey: 32000])
  a.expectsMediaDataInRealTime = false; w.add(a); ain = a
}
w.startWriting(); w.startSession(atSourceTime: .zero)
if let v = vin, let ad = ad {
  for i in 0..<5 {
    while !v.isReadyForMoreMediaData { usleep(1000) }
    var pb: CVPixelBuffer?; CVPixelBufferPoolCreatePixelBuffer(nil, ad.pixelBufferPool!, &pb)
    CVPixelBufferLockBaseAddress(pb!, []); memset(CVPixelBufferGetBaseAddress(pb!), 128, CVPixelBufferGetDataSize(pb!)); CVPixelBufferUnlockBaseAddress(pb!, [])
    ad.append(pb!, withPresentationTime: CMTime(value: CMTimeValue(i), timescale: 10))
  }
  v.markAsFinished()
}
if let a = ain {
  let frames = 22050
  var asbd = AudioStreamBasicDescription(mSampleRate: 44100, mFormatID: kAudioFormatLinearPCM, mFormatFlags: kLinearPCMFormatFlagIsSignedInteger | kLinearPCMFormatFlagIsPacked, mBytesPerPacket: 2, mFramesPerPacket: 1, mBytesPerFrame: 2, mChannelsPerFrame: 1, mBitsPerChannel: 16, mReserved: 0)
  var fmt: CMAudioFormatDescription?; CMAudioFormatDescriptionCreate(allocator: nil, asbd: &asbd, layoutSize: 0, layout: nil, magicCookieSize: 0, magicCookie: nil, extensions: nil, formatDescriptionOut: &fmt)
  var bb: CMBlockBuffer?; CMBlockBufferCreateWithMemoryBlock(allocator: nil, memoryBlock: nil, blockLength: frames * 2, blockAllocator: nil, customBlockSource: nil, offsetToData: 0, dataLength: frames * 2, flags: kCMBlockBufferAssureMemoryNowFlag, blockBufferOut: &bb)
  CMBlockBufferFillDataBytes(with: 0, blockBuffer: bb!, offsetIntoDestination: 0, dataLength: frames * 2)
  var sb: CMSampleBuffer?; CMAudioSampleBufferCreateReadyWithPacketDescriptions(allocator: nil, dataBuffer: bb!, formatDescription: fmt!, sampleCount: frames, presentationTimeStamp: .zero, packetDescriptions: nil, sampleBufferOut: &sb)
  while !a.isReadyForMoreMediaData { usleep(1000) }
  a.append(sb!); a.markAsFinished()
}
let sem = DispatchSemaphore(value: 0); w.finishWriting { sem.signal() }; sem.wait()
print(w.status == .completed ? "ok" : "failed: \(String(describing: w.error))")
