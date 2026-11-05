import functools, sys
import chromadb, ollama

EMBED_MODEL = "nomic-embed-text"
DB_PATH, COLLECTION = "chroma_db", "orca_manual"


def embed(texts, prefix="search_document: "):
    return ollama.embed(EMBED_MODEL, input=[prefix + t for t in texts]).embeddings


def create_collection():
    client = chromadb.PersistentClient(DB_PATH)
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


@functools.cache
def collection():
    return chromadb.PersistentClient(DB_PATH).get_collection(COLLECTION)


def retrieve(question, k=5):
    r = collection().query(
        query_embeddings=embed([question], "search_query: "),
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    return [{"text": t, "distance": d, **m}
            for t, m, d in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])]


if __name__ == "__main__":
    for hit in retrieve(" ".join(sys.argv[1:]) or "how many roots in CASSCF"):
        print(f"{hit['distance']:.3f}  p{hit['page']:<5} {hit['heading']}")