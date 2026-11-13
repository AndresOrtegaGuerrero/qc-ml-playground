from pydantic import Field, model_validator
from .base import SchemaModel
from .blocks import OrcaBlock
from .header import Header, Directives, Resources
from .molecule import Molecule
from .vocab import BLOCKS

# a block setting that has exactly one home elsewhere is moved there (repair), not rejected
MOVES = {("scf", "convergence"): ("header", "scf_convergence"),
         ("geom", "convergence"): ("header", "opt_convergence"),
         ("method", "maxcore"): ("resources", "maxcore"),
         ("pal", "nprocs"): ("resources", "nprocs"),
         ("scf", "charge"): ("molecule", "charge"),
         ("scf", "mult"): ("molecule", "mult")}
BASIS_KEYS = {"basis": "main", "auxj": "aux", "auxc": "aux", "auxjk": "aux", "aux": "aux", "auxbasis": "aux"}
CONV = {"verytight": "VeryTight", "tight": "Tight", "normal": "Normal", "loose": "Loose", "sloppy": "Sloppy", "strong": "Strong"}

# where the things people put in a block usually belong (used when a setting is unknown)
HINTS = {"method": "the method goes in header.method, the run type in header.tasks",
         "scf": "use %scf for maxiter, guess, ...; convergence is header.scf_convergence",
         "geom": "an optimisation is 'Opt' in header.tasks; use %geom for maxiter, constraints, ...",
         "basis": "per-element bases go in header.basis.per_element / per_element_aux; main and auxiliary bases in header.basis",
         "freq": "frequencies are 'Freq' in header.tasks; use %freq only for its own settings"}


class OrcaInput(SchemaModel):
    header: Header
    molecule: Molecule
    directives: Directives = Field(default_factory=Directives)
    resources: Resources = Field(default_factory=Resources)
    blocks: list[OrcaBlock] = Field(default_factory=list,
                                    description="only for settings with no header field (e.g. %casscf, %scf maxiter, %geom); never for tasks, convergence, basis or parallelism")

    def block_name(self, b):
        return b.name if b.kind == "generic" else b.kind

    def block(self, name):
        return next((b for b in self.blocks if self.block_name(b) == name), None)

    @model_validator(mode="before")
    @classmethod
    def move_misplaced(cls, d):
        if not isinstance(d, dict):
            return d
        blocks = d.get("blocks") or []
        for blk in blocks:
            if str(blk.get("name")).lower() == "basis":                      # %basis AuxJ/AuxC/Basis -> header.basis
                hb = d.setdefault("header", {}).setdefault("basis", {})
                for key in list(blk.get("settings") or {}):
                    if (dest := BASIS_KEYS.get(key.lower())):
                        val = blk["settings"].pop(key)
                        hb.setdefault("aux", []).append(val) if dest == "aux" else hb.setdefault("main", val)
            for key in list(blk.get("settings") or {}):
                if (dest := MOVES.get((str(blk.get("name")).lower(), key.lower()))):
                    val = blk["settings"].pop(key)
                    if dest[1].endswith("convergence"):
                        val = CONV.get(str(val).lower(), val)
                    d.setdefault(dest[0], {}).setdefault(dest[1], val)      # a value already in place wins
        d["blocks"] = [b for b in blocks if b.get("settings") or b.get("raw") or "nel" in b]
        return d

    @model_validator(mode="after")
    def consistent(self):
        names = [self.block_name(b) for b in self.blocks]
        if len(names) != len(set(names)):
            raise ValueError("each block may appear only once" + ("; for several multiplicities use one casscf block with "
                             "mult [1, 3] and nroots [2, 3]" if names.count("casscf") > 1 else ""))
        if self.header.method.upper() == "CASSCF" and self.block("casscf") is None:
            raise ValueError("method CASSCF requires a casscf block")
        for b in self.blocks:
            if b.kind != "generic":
                continue
            unknown = set(b.settings) - set(BLOCKS[b.name].model_fields)
            if unknown:
                raise ValueError(f"%{b.name} does not accept {sorted(unknown)}. {HINTS.get(b.name, '')}".strip())
        hb = self.header.basis
        if (hb.per_element or hb.per_element_aux) and self.block("basis") is not None:
            raise ValueError("per-element bases are rendered as %basis; move the basis block's settings to header.basis "
                             "(main, aux, per_element, per_element_aux) and remove the block")
        return self