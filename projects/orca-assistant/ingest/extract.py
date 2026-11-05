import json, sys
import pymupdf

TOC = json.load(open("data/toc.json"))
BOX_KINDS = {(0.82, 0.87, 0.98): "note"}      # confirm colours in the PDF


def section_at(page):
    before = [t for t in TOC if t["page"] <= page]
    return max(before, key=lambda t: (t["page"], t["depth"]))["path"] if before else ""


def box_kind(fill):
    r, g, b = (round(c, 2) for c in fill)
    if r == g == b and r > 0.8:                 # any light grey
        return "code"
    return BOX_KINDS.get((r, g, b))


def page_boxes(page):
    boxes = []
    for d in page.get_drawings():
        r = d["rect"]
        if d["fill"] and r.width > 200 and r.height > 15:
            if k := box_kind(d["fill"]):
                boxes.append((r, k))
    return boxes


def box_at(point, boxes):
    for rect, kind in boxes:
        if rect.contains(point):
            return kind
    return None


def merge_same_row(elements, tol=2.0):
    """Join code lines on the same line."""
    out = []
    for el in elements:
        prev = out[-1] if out else None
        if prev and prev["code"] and el["code"] and abs(prev["y0"] - el["y0"]) < tol:
            prev["text"] += " " + el["text"]
        else:
            out.append(el)
    return out


def page_elements(page):
    boxes = page_boxes(page)
    top, bottom = 60, page.rect.height - 70
    elements = []
    for block in page.get_text("dict", sort=True)["blocks"]:
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            bbox = pymupdf.Rect(line["bbox"])
            if not text or bbox.y0 < top or bbox.y1 > bottom:
                continue
            font = line["spans"][0]["font"]
            box = box_at((bbox.tl + bbox.br) / 2, boxes)
            elements.append({
                "text": text,
                "font": line["spans"][0]["font"],
                "box": box,
                "code": box == "code" or "Mono" in font,
                "y0": round(bbox.y0, 1),
            })
    return merge_same_row(elements)


def extract(pdf, out="data/pages.jsonl"):
    with pymupdf.open(pdf) as doc, open(out, "w") as f:
        for i, page in enumerate(doc, 1):
            record = {"page": i, "label": page.get_label(),
                      "section": section_at(i), "elements": page_elements(page)}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            if i % 100 == 0:
                print(f"{i}/{len(doc)}", file=sys.stderr)


if __name__ == "__main__":
    extract(sys.argv[1] if len(sys.argv) > 1 else "data/raw/orca_6_1_1_manual.pdf")