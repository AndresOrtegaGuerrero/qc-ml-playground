import json, sys
from pathlib import Path
from pypdf import PdfReader



def walk(reader, items, depth=0, path=()):
    """Recursively walk the PDF outline, yielding (depth, title, page_number, path)."""
    for item in items:
        if isinstance(item, list):
            yield from walk(reader, item, depth + 1, path)
        else:
            path = path[:depth] + (item.title,)
            yield {
                "title": item.title,
                "page": reader.get_destination_page_number(item) + 1,
                "depth": depth,
                "path": " > ".join(path),
            }


def main(pdf):
    reader = PdfReader(pdf)
    toc = list(walk(reader, reader.outline))
    Path("data/raw/toc.json").write_text(json.dumps(toc, indent=1))
    print(f"{len(toc)} sections, {len(reader.pages)} pages")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/raw/orca_6_1_1_manual.pdf")