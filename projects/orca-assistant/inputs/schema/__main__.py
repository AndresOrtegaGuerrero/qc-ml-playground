import json, sys
from pydantic import ValidationError
from . import OrcaInput, feedback


def main(argv):

    if argv[:1] == ["schema"]:
        print(json.dumps(OrcaInput.model_json_schema(), indent=2))
    elif argv[:1] == ["validate"] and len(argv) == 2:
        try:
            input = OrcaInput.model_validate_json(open(argv[1]).read())
            print(input.model_dump_json(indent=2, exclude_none=True))
        except ValidationError as e:
            sys.exit(feedback(e))
    else:
        sys.exit(f"Usage: python -m inputs.schema {argv[0]} schema|validate <FILE.json>")


main(sys.argv[1:])