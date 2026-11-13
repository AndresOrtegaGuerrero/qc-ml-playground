import argparse
import ollama
from pydantic import ValidationError
from rag.retrieve import retrieve
from rag.answer import format_context
from inputs.schema import OrcaInput, feedback
from inputs.adapter import to_opi_input, render


SYSTEM = """You turn a request into an ORCA input description that matches the JSON schema.
Use only keywords that appear in the manual excerpts or that you are certain exist in ORCA.
Put basis sets in header.basis, convergence in the *_convergence fields, parallelism in resources.
Fill only what the request asks for or clearly implies. An unset field is correct; an invented one is wrong.
"""

SCHEMA = OrcaInput.model_json_schema()


def field_guide(schema, prefix="", defs=None):
    """'path: description' lines: Ollama's format= only constrains tokens, the model never reads the schema."""
    defs = defs or schema.get("$defs", {})
    for name, f in schema.get("properties", {}).items():
        if "$ref" in f:
            f = defs[f["$ref"].split("/")[-1]]
        if (desc := f.get("description")):
            yield f"{prefix}{name}: {desc}"
        if "properties" in f:
            yield from field_guide(f, f"{prefix}{name}.", defs)
        for opt in f.get("items", {}).get("oneOf", []):                      # list of block variants
            blk = defs[opt["$ref"].split("/")[-1]]
            kind = blk["properties"]["kind"].get("default", "block")
            yield from field_guide(blk, f"{prefix}{name}[{kind}].", defs)


SYSTEM += """basis.main is the orbital basis (def2-TZVP); basis.aux only holds names ending in /J, /JK or /C.
molecule.xyz stays unset when a structure file is named. The shell treatment (unrestricted, ...) goes in header.shell, never in method.
An optimisation is tasks ["Opt"], frequencies ["Freq"]; a single point needs nothing.

Fields:
""" + "\n".join(field_guide(SCHEMA))

EXAMPLE = [{"role": "user", "content": "Request: UKS B3LYP def2-SVP single point of the doublet cation in mol.xyz, 4 cores"},
           {"role": "assistant", "content": """{"header": {"method": "b3lyp", "basis": {"main": "def2-SVP"}, "tasks": ["SP"], "shell": "unrestricted"},
 "molecule": {"charge": 1, "mult": 2, "xyzfile": "mol.xyz"}, "resources": {"nprocs": 4}, "blocks": []}"""}]

RETRY = ("That input was rejected:\n{msg}\n\nReturn the same JSON, changing only what is needed to fix this; "
         "keep every other field as it was.\nRequest: {request}")


def generate(request, model="qwen2.5:14b", k=5, attempts=3):
    """-> (OrcaInput | None, last_reply_json, errors, hits). None means unresolved after all attempts."""
    hits = retrieve(request, k)
    messages = [{"role": "system", "content": SYSTEM}, *EXAMPLE,
                {"role": "user", "content": f"Manual excerpts:\n{format_context(hits)}\n\nRequest: {request}"}]
    errors = []
    options = {"temperature": 0, "num_predict": 1500}
    for _ in range(attempts):
        reply = ollama.chat(model, messages=messages, format=SCHEMA, options=options).message.content
        try:
            inp = OrcaInput.model_validate_json(reply)
            to_opi_input(inp)                       # second gate: orca-pi
            return inp, reply, errors, hits
        except (ValidationError, ValueError, FileNotFoundError) as e:
            errors.append(feedback(e))
            if "Invalid JSON" in errors[-1]:                 # grammar walked into a repetition loop: nudge the sampling
                options = {**options, "temperature": 0.15, "repeat_penalty": 1.1}
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": RETRY.format(msg=errors[-1], request=request)}]
    return None, reply, errors, hits


def main():
    parser = argparse.ArgumentParser(description="Generate ORCA input from a natural-language request.")
    parser.add_argument("request", nargs="+", help="Natural-language calculation request.")
    parser.add_argument("--json", action="store_true", help="Output the generated input as JSON.")
    parser.add_argument("--both", action="store_true", help="Output both JSON and ORCA input.")
    parser.add_argument("--model", default="qwen2.5:14b")
    args = parser.parse_args()
    request = " ".join(args.request)

    inp, reply, errors, hits = generate(request, model=args.model)

    if errors:
        print(f"# {len(errors)} rejected attempt(s):")
        print(*errors, sep="\n---\n")
    if inp is None:                                 # graceful failure: best attempt + what is still wrong
        print("\n# UNRESOLVED after all attempts; last attempt (not valid):\n")
        print(reply)
        raise SystemExit(1)

    if not args.json:
        print("Generated ORCA input:\n")
        print(render(inp))
    if args.json or args.both:
        print("\nGenerated JSON:\n")
        print(inp.model_dump_json(indent=2, exclude_none=True))


if __name__ == "__main__":
    main()
