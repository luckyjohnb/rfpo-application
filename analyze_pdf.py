"""Analyze PDF text positions for layout comparison."""
import fitz
import sys

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "current_snapshot.pdf"
doc = fitz.open(pdf_path)
page = doc[0]
blocks = page.get_text("dict")["blocks"]

print(f"Page size: {page.rect.width:.1f} x {page.rect.height:.1f}")
print(f"{'X0':>6} {'Y0':>6} {'X1':>6} {'Y1':>6}  {'Size':>5} {'Font':<20} Text")
print("-" * 100)

for b in blocks:
    if "lines" not in b:
        continue
    for line in b["lines"]:
        for span in line["spans"]:
            text = span["text"].strip()
            if not text:
                continue
            bbox = span["bbox"]
            print(f"{bbox[0]:6.1f} {bbox[1]:6.1f} {bbox[2]:6.1f} {bbox[3]:6.1f}  {span['size']:5.1f} {span['font']:<20} {text}")

# Also get drawings/lines
print("\n--- Lines/Rectangles ---")
drawings = page.get_drawings()
for d in drawings:
    for item in d["items"]:
        kind = item[0]
        if kind == "l":  # line
            p1, p2 = item[1], item[2]
            print(f"LINE: ({p1.x:.1f},{p1.y:.1f}) -> ({p2.x:.1f},{p2.y:.1f})  width={d.get('width', 0):.2f}")
        elif kind == "re":  # rectangle
            rect = item[1]
            print(f"RECT: ({rect.x0:.1f},{rect.y0:.1f}) -> ({rect.x1:.1f},{rect.y1:.1f})  width={d.get('width', 0):.2f}")

doc.close()
