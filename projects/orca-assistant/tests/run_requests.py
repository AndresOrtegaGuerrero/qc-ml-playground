"""Run data/requests.jsonl through generate and score: needs Ollama, so not a pytest.
usage: python tests/run_requests.py [--model qwen2.5:14b] [--only id]"""
import argparse, json, pathlib
from inputs.generate import generate
from inputs.adapter import render

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="qwen2.5:14b")
ap.add_argument("--only")
args = ap.parse_args()

out = pathlib.Path("data/runs"); out.mkdir(exist_ok=True)
score = []
for line in open("data/requests.jsonl"):
    case = json.loads(line)
    if args.only and case["id"] != args.only:
        continue
    inp, reply, errors, hits = generate(case["request"], model=args.model)
    text = render(inp) if inp else ""
    missing = [e for e in case["expect"] if e.lower() not in text.lower()]
    status = "UNRESOLVED" if inp is None else ("PASS" if not missing else "MISSING " + ", ".join(missing))
    score.append(status.split()[0])
    print(f"{case['id']:18} {len(errors)} retries  {status}")
    (out / f"{case['id']}.txt").write_text(f"# {case['request']}\n# {case['note']}\n# retrieved: " + "; ".join(f"p{h['page']} {h['heading']}" for h in hits)
        + f"\n\n{text or reply}\n\n# errors:\n" + "\n---\n".join(errors))
print(f"\n{score.count('PASS')}/{len(score)} pass, {score.count('UNRESOLVED')} unresolved; details in data/runs/")
