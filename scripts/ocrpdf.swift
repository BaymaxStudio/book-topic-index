import Foundation
import PDFKit
import Vision
import AppKit

// ocrpdf <pdf> <outdir> [firstPage] [lastPage]
let a = CommandLine.arguments
guard a.count >= 3 else {
  FileHandle.standardError.write("usage: ocrpdf <pdf> <outdir> [first] [last]\n".data(using: .utf8)!)
  exit(1)
}
let pdfPath = a[1]
let outDir  = a[2]
let first   = a.count > 3 ? (Int(a[3]) ?? 1) : 1
let lastArg = a.count > 4 ? (Int(a[4]) ?? Int.max) : Int.max

guard let doc = PDFDocument(url: URL(fileURLWithPath: pdfPath)) else {
  FileHandle.standardError.write("cannot open pdf\n".data(using: .utf8)!); exit(2)
}
let total = doc.pageCount
let last = min(lastArg, total)
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

let jsonlPath = outDir + "/lines.jsonl"
let txtPath   = outDir + "/text.txt"
FileManager.default.createFile(atPath: jsonlPath, contents: nil)
FileManager.default.createFile(atPath: txtPath, contents: nil)
let jh = try! FileHandle(forWritingTo: URL(fileURLWithPath: jsonlPath))
let th = try! FileHandle(forWritingTo: URL(fileURLWithPath: txtPath))

let dpi = 300.0
let scale = dpi / 72.0

func esc(_ s: String) -> String {
  var o = ""
  for ch in s.unicodeScalars {
    switch ch {
    case "\"": o += "\\\""
    case "\\": o += "\\\\"
    case "\n": o += "\\n"
    case "\r": o += "\\r"
    case "\t": o += "\\t"
    default:
      if ch.value < 0x20 { o += String(format: "\\u%04x", ch.value) } else { o.unicodeScalars.append(ch) }
    }
  }
  return o
}

for i in (first-1)..<last {
  autoreleasepool {
    guard let page = doc.page(at: i), let cgPage = page.pageRef else { return }
    let box = cgPage.getBoxRect(.mediaBox)
    let w = Int(box.width * scale), h = Int(box.height * scale)
    guard w > 0, h > 0,
          let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8,
                              bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    ctx.drawPDFPage(cgPage)
    guard let cg = ctx.makeImage() else { return }

    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["zh-Hans", "en-US"]
    req.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([req]) } catch { return }

    // 收集行，按 y 上→下、x 左→右排序
    struct L { let t: String; let x: Double; let y: Double; let w: Double; let h: Double; let c: Float }
    var lines: [L] = []
    for obs in (req.results ?? []) {
      guard let cand = obs.topCandidates(1).first else { continue }
      let bb = obs.boundingBox   // 归一化，原点左下
      lines.append(L(t: cand.string, x: Double(bb.minX), y: Double(1 - bb.maxY),
                     w: Double(bb.width), h: Double(bb.height), c: cand.confidence))
    }
    lines.sort { $0.y != $1.y ? $0.y < $1.y : $0.x < $1.x }

    let pageNo = i + 1
    var jline = "{\"page\":" + String(pageNo) + ",\"w\":" + String(w) + ",\"h\":" + String(h) + ",\"lines\":["
    var tbuf = ""
    for (k, l) in lines.enumerated() {
      if k > 0 { jline += "," }
      jline += "{\"t\":\"" + esc(l.t) + "\",\"x\":" + String(format: "%.4f", l.x)
             + ",\"y\":" + String(format: "%.4f", l.y)
             + ",\"w\":" + String(format: "%.4f", l.w)
             + ",\"h\":" + String(format: "%.4f", l.h)
             + ",\"c\":" + String(format: "%.2f", l.c) + "}"
      tbuf += l.t + "\n"
    }
    jline += "]}\n"
    jh.write(jline.data(using: .utf8)!)
    th.write(("\n===== [PDF p." + String(pageNo) + "] =====\n" + tbuf).data(using: .utf8)!)
    if pageNo % 10 == 0 || pageNo == first || pageNo == last {
      FileHandle.standardError.write(("page " + String(pageNo) + "/" + String(last) + " lines=" + String(lines.count) + "\n").data(using: .utf8)!)
    }
  }
}
jh.closeFile(); th.closeFile()
print("DONE pages " + String(first) + "-" + String(last) + " of " + String(total))
