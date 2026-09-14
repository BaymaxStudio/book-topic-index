import Foundation
import PDFKit
import AppKit

// markpdf <in.pdf> <annotations.json> <out.pdf>
let a = CommandLine.arguments
guard a.count >= 4 else {
  FileHandle.standardError.write("usage: markpdf <in.pdf> <ann.json> <out.pdf>\n".data(using: .utf8)!)
  exit(1)
}
guard let doc = PDFDocument(url: URL(fileURLWithPath: a[1])) else {
  FileHandle.standardError.write("cannot open pdf\n".data(using: .utf8)!); exit(2)
}
let data = try! Data(contentsOf: URL(fileURLWithPath: a[2]))
let anns = (try! JSONSerialization.jsonObject(with: data)) as! [[String: Any]]

var count = 0
for entry in anns {
  guard let pno = entry["page"] as? Int,
        let rects = entry["rects"] as? [[Double]],
        let page = doc.page(at: pno - 1) else { continue }
  let b = page.bounds(for: .mediaBox)
  let label = entry["label"] as? String ?? ""
  for r in rects where r.count >= 4 {
    let x = r[0] * Double(b.width)
    let yTop = r[1] * Double(b.height)
    let w = r[2] * Double(b.width)
    let h = r[3] * Double(b.height)
    let rect = CGRect(x: b.minX + CGFloat(x) - 0.8,
                      y: b.minY + b.height - CGFloat(yTop) - CGFloat(h) - 0.8,
                      width: CGFloat(w) + 1.6,
                      height: CGFloat(h) + 1.6)
    let ann = PDFAnnotation(bounds: rect, forType: .highlight, withProperties: nil)
    ann.color = NSColor.yellow.withAlphaComponent(0.35)
    if !label.isEmpty { ann.contents = label }
    page.addAnnotation(ann)
    count += 1
  }
}
doc.write(to: URL(fileURLWithPath: a[3]))
print("annotation-rects=\(count)")
