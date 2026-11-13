from typing import Annotated, Literal
from pydantic import Field, field_validator, model_validator, Discriminator, Tag
from .base import SchemaModel
from .vocab import BlockName, PTMethod, Scalar, norm

PT = {norm(p): p for p in PTMethod.__args__}        # 'SC-NEVPT2', 'sc_nevpt2' -> 'sc_nevpt2'



class CasscfBlock(SchemaModel):
    kind: Literal["casscf"] = "casscf"
    nel: int = Field(gt=0, description="active electrons")
    norb: int = Field(gt=0, description="active orbitals")
    nroots: int | list[int] = Field(1, description="roots, or one entry per multiplicity block")
    mult: int | list[int] | None = Field(None, description="multiplicity per block; default: the molecule's")
    ptmethod: PTMethod | None = Field(None, description="NEVPT2/CASPT2 variant on top of CASSCF")
    raw: str | None = Field(None, description="verbatim lines appended inside the block, e.g. nested sub-blocks")
    extra: dict[str, Scalar] = Field(default_factory=dict, description="other %casscf keywords, e.g. {\"maxiter\": 1000, \"donto\": true}")

    @model_validator(mode="before")
    @classmethod
    def accept_generic_shape(cls, d):             # {"name": "casscf", "settings": {...}} is the same block, spelled differently
        if not isinstance(d, dict):
            return d
        d = {k.lower(): v for k, v in d.items() if k != "name"}
        settings = {k.lower(): v for k, v in (d.pop("settings", None) or {}).items()}
        own = set(cls.model_fields) - {"extra", "raw", "kind"}
        d["extra"] = {**{k: v for k, v in settings.items() if k not in own}, **(d.get("extra") or {})}
        return {**{k: v for k, v in settings.items() if k in own}, **d}

    @field_validator("nroots", "mult", mode="before")
    @classmethod
    def comma_list(cls, v):                       # "2,3" -> [2, 3]
        return [int(x) for x in v.split(",")] if isinstance(v, str) and "," in v else v

    @field_validator("ptmethod", mode="before")
    @classmethod
    def canonical_pt(cls, v):
        if v is None or norm(v) in PT:
            return None if v is None else PT[norm(v)]
        raise ValueError(f"ptmethod {v!r}: use one of {list(PT.values())}; plain NEVPT2 means sc_nevpt2 or fic_nevpt2")

    @model_validator(mode="after")
    def active_space(self):
        if self.nel > 2 * self.norb:
            raise ValueError(f"{self.nel} electrons cannot fit in {self.norb} orbitals; nel must be at most 2*norb")
        if isinstance(self.mult, list) and isinstance(self.nroots, list) and len(self.mult) != len(self.nroots):
            raise ValueError("mult and nroots lists must have the same length: one nroots entry per multiplicity")
        return self


class GenericBlock(SchemaModel):
    kind: Literal["generic"] = "generic"
    name: BlockName
    settings: dict[str, Scalar] = Field(default_factory=dict, description="keywords of that block")
    raw: str | None = Field(None, description="verbatim block body when settings cannot express it")

    @field_validator("settings", mode="before")
    @classmethod
    def lower_keys(cls, v):                       # ORCA ignores case, OPI fields are lowercase
        return {k.lower(): x for k, x in v.items()}

    @model_validator(mode="after")
    def not_empty(self):
        if not self.raw and not self.settings:
            raise ValueError(f"empty %{self.name} block: remove it. Opt/Freq go in header.tasks, "
                             "convergence in header.opt_convergence / scf_convergence, cores and memory in resources")
        return self

def block_kind(v):
    if isinstance(v, dict):
        return "casscf" if v.get("kind") == "casscf" or v.get("name") == "casscf" or "nel" in v else "generic"
    return getattr(v, "kind", None)

OrcaBlock = Annotated[
    Annotated[CasscfBlock, Tag("casscf")] | Annotated[GenericBlock, Tag("generic")],
    Discriminator(block_kind),
]