from pydantic import BaseModel, ConfigDict, ValidationError


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def feedback(e):                     # "path: message" lines, no pydantic URLs or echoed input
    if isinstance(e, ValidationError):
        return "\n".join(f"{'.'.join(map(str, x['loc']))}: {x['msg'][:300]}" for x in e.errors())
    return str(e)
