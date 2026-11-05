import json
from rag.retrieve import retrieve

KS = (1,3, 5)


def hits(question, results):
    return {
        "page": any(result["page"]-question["page"] <= 1 for result in results), 
        "section": any(result["section"].startswith(question["section"]) for result in results), 
        "keyword": any(question["keyword"].lower() in result["text"].lower() for result in results),
    }



def evaluate(eval_file="data/eval.jsonl", k_chunks=KS):
    questions = [json.loads(l) for l in open(eval_file)]
    rows = []

    for question in questions:
        results = retrieve(question["question"], max(k_chunks))
        rows.append({k: hits(question, results) for k in k_chunks})
    print(f"{'':10}" + "".join(f"{'k=' + str(k):>8}" for k in k_chunks))
    for check in ("page", "section", "keyword"):
        print(f"{check:10}" + "".join(f"{sum(r[k][check] for r in rows) / len(rows):8.2f}" for k in k_chunks))
    return rows


if __name__ == "__main__":
    rows = evaluate()
    questions = [json.loads(l) for l in open("data/eval.jsonl")]
    for q, r in zip(questions, rows):
        if not r[5]["page"]:
            print("MISS", q["id"], q["question"])




