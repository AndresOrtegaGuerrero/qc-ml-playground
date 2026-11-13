from pydantic import Field, field_validator, model_validator
from .base import SchemaModel
from .vocab import AUX_BASES, BASES, canonical, norm, resolve
from opi.utils.element import Element

class Basis(SchemaModel):
    main: str | None = Field(None, description="the orbital basis set named in the request, e.g. def2-TZVP; leave unset for composite methods (-3c, xTB) which carry their own")
    aux: list[str] = Field(default_factory=list,
                                   description="auxiliary (fitting) basis sets named in the request, e.g. ['def2/J', 'def2-SVP/C']; only if RI/RIJCOSX is asked for or they are named; the role (J, JK, C) follows from the name")
    per_element: dict[str, str] = Field(default_factory=dict, description='orbital basis override for one element, e.g. {"Zn": "def2-TZVP"}; only if requested')
    per_element_aux: dict[str, str] = Field(default_factory=dict, description='auxiliary basis override for one element, e.g. {"Zn": "def2-TZVP/C"}; only if requested')

    @model_validator(mode="before")
    @classmethod
    def aux_not_in_per_element(cls, data):        # repair: a basis named for one element is per-element, not global
        if not isinstance(data, dict):
            return data
        per = {norm(b) for b in (data.get("per_element_aux") or {}).values()}
        main = norm(data.get("main") or "")
        return {**data, "aux": [a for a in (data.get("aux") or []) if norm(a) not in per],
                "per_element": {e: b for e, b in (data.get("per_element") or {}).items() if norm(b) != main}}

    @field_validator("aux", mode="before")
    @classmethod
    def canonical_aux(cls, v):
        return [resolve(AUX_BASES, x, "auxiliary basis") for x in v]

    @field_validator("main", mode="before")
    @classmethod
    def canonical_main(cls, v):
        return None if v is None else canonical(BASES, v)      # unknown spellings pass through (BasisSet box may be incomplete)

    def aux_by_role(self):
        """{'j'|'jk'|'c': basis} from the name suffix; the role is derived, never asked."""
        roles = {}
        for bs in self.aux:
            n = norm(bs)
            role = next((r for r in ("jk", "j", "c") if n.endswith(r)), None)
            if role is None:
                raise ValueError(f"cannot tell the role of auxiliary basis {bs!r}; auxiliary bases end in /J, /JK or /C (e.g. def2/J, def2-SVP/C)")
            if role in roles:
                raise ValueError(f"two auxiliary bases for the role /{role.upper()}: {roles[role]!r} and {bs!r}; keep one")
            roles[role] = bs
        return roles

    @model_validator(mode="after")
    def consistent(self):
        roles = self.aux_by_role()
        if "j" in roles and "jk" in roles:
            raise ValueError("choose a /J or a /JK auxiliary basis, not both; keep the one the request names")
        for field in ("per_element", "per_element_aux"):
            if len(getattr(self, field)) > 1:
                raise ValueError(f"{field}: one element only for now (OPI's %basis renders a single newgto line); "
                         "keep the element the request singles out")
        return self

    @field_validator("per_element", "per_element_aux", mode="before")
    @classmethod
    def element_keys(cls, v):
        out = {}
        for el, bs in v.items():
            try:
                out[str(Element(el))] = bs
            except ValueError:
                raise ValueError(f"{el!r} is not an element symbol; the default basis goes in basis.main, "
                                f"per_element only holds exceptions such as {{'Zn': 'def2-TZVP'}}")
        return out