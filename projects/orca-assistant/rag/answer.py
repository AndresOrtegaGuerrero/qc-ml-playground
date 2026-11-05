
import sys
import ollama 
from rag.retrieve import retrieve

CHAT_MODEL = "qwen2.5:7b"


SYSTEM = """
You are an expert assistant for the ORCA quantum chemistry program.

Your task is to answer questions using ONLY the provided manual content.

Follow these rules strictly:

1. Do not use external knowledge or assumptions.
2. If excerpt do not contain enough information, respond that information is not provided in the manual.
3. Do not invent commands, keywords, input parameters, or syntax.
4. When explaining input syntax, provide a minimal valid example.
   in a code block.
5. If the manual describes a limitation or warning, include when relevant.
6. Cite the section you used, e.g. (3.13.3 Basic Usage, p. 359)
"""


def format_context(hits):

    return "\n\n".join(
        f"[{i}] Section {h['heading'] or h['section'].split(' > ')[-1]}, p. {h['label']}\n{h['text']}"
        for i, h in enumerate(hits, 1)
    )

def build_messages(question, hits):
    context = format_context(hits)
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Manual excerpts: \n{context}\n\nQuestion: {question}"},
    ]


def answer(question, k=5, model=CHAT_MODEL):
    hits = retrieve(question, k)
    messages = build_messages(question, hits)
    reply = ollama.chat(model, messages=messages, options={"temperature": 0.0})
    return reply.message.content, hits


if __name__ == "__main__":
    text, hits = answer(" ".join(sys.argv[1:]))
    print(text)
    print("\nSources:", ", ".join(f"p{h['page']} {h['heading']}" for h in hits))