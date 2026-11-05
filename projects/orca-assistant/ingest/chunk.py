import json, re, sys
import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")
HEADING = re.compile(r"^\d+(\.\d+)+\s+\S")
PREFIX = {"code": "    ", "heading": "## ", "note": "> "}


def kind(el):
    if el["box"] == "code" or "Mono" in el["font"]:
        return "code"
    if "Bold" in el["font"] and HEADING.match(el["text"]):
        return "heading"
    return el["box"] or "text"


def blocks(elements):
    out = []
    for el in elements:
        k = kind(el)
        if out and out[-1]["kind"] == k and k != "heading":
            out[-1]["text"] += "\n" + el["text"]
        else:
            out.append({"kind": k, "text": el["text"]})
    return out


def render(block):
    p = PREFIX.get(block["kind"], "")
    return "\n".join(p + line for line in block["text"].splitlines())


def ntok(s):
    return len(ENC.encode(s))


def pack(blocks, size=500, heading=None):
    chunks, buf = [], []
    for b in blocks:
        if b["kind"] == "heading":
            if buf:
                chunks.append((heading, buf))
            heading, buf = b["text"], []
            continue
        if buf and ntok("\n".join(render(x) for x in buf + [b])) > size:
            chunks.append((heading, buf))
            buf = []
        buf.append(b)
    if buf:
        chunks.append((heading, buf))
    return chunks


def chunk_pages(pages, size=500):
    heading = None
    for p in pages:
        for k, (h, bs) in enumerate(pack(blocks(p["elements"]), size, heading)):
            heading = h
            text = "\n".join(render(b) for b in bs)
            if ntok(text) < 30:
                continue
            yield {"id": f"p{p['page']}-{k}", "page": p["page"], "label": p["label"],
                   "section": p["section"], "heading": heading, "text": text}


if __name__ == "__main__":
    pages = (json.loads(l) for l in open("data/pages.jsonl"))
    n = 0
    with open("data/chunks.jsonl", "w") as f:
        for c in chunk_pages(pages):
            f.write(json.dumps(c) + "\n")
            n += 1
    print(n, "chunks", file=sys.stderr)