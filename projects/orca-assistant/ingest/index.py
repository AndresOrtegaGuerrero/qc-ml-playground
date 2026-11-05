import json, sys
from rag.retrieve import embed, create_collection


def index(chunks_file="data/chunks.jsonl", batch=64):
    chunks = [json.loads(l) for l in open(chunks_file)]
    col = create_collection()
    for i in range(0, len(chunks), batch):
        part = chunks[i:i + batch]
        col.upsert(
            ids=[c["id"] for c in part],
            embeddings=embed([c["text"] for c in part]),
            documents=[c["text"] for c in part],
            metadatas=[{"page": c["page"], "label": c["label"], "section": c["section"],
                        "heading": c["heading"] or ""} for c in part],
        )
        print(f"{i + len(part)}/{len(chunks)}", file=sys.stderr)
    print(col.count(), "in collection", file=sys.stderr)


if __name__ == "__main__":
    index()