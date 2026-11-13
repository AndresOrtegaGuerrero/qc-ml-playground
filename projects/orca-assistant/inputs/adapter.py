
import functools
from pathlib import Path

from pydantic import PrivateAttr

from opi.input import simple_keywords as sk
from opi.input.blocks import BlockCasscf, BlockBasis
from opi.input.blocks.block_basis import NewBasis
from opi.input.core import Input
from opi.input.structures.structure import Structure
from opi.input.structures.structure_file import XyzFile, BaseStructureFile

from inputs.schema import OrcaInput, CasscfBlock
from inputs.schema.vocab import BLOCKS, METHODS, KEYWORDS, BASES, AUX_BASES, canonical, shell_keyword


# ---- "!" line -----------------------------------------------------------
def kw(name):                        # catalogue lookup; plain keyword only for what OPI does not list (basis names)
    return KEYWORDS.get(canonical(KEYWORDS, name)) or sk.SimpleKeyword(name)


def bang_keywords(h, moread):
    b = h.basis
    out = [METHODS[h.method]]                                  # Literal: always present
    if b.main:
        out.append(BASES.get(b.main) or sk.SimpleKeyword(b.main))
    out += [AUX_BASES[x] for x in b.aux]
    for t in h.tasks:
        if t == "SP":
            continue
        out.append(getattr(sk.Opt, f"{h.opt_convergence or ''}OPT".upper()) if t == "Opt" else kw(t))
    if h.scf_convergence:
        out.append(getattr(sk.Scf, f"{h.scf_convergence}SCF".upper()))
    if h.shell:
        out.append(kw(shell_keyword(h.method, h.shell)))
    if moread:
        out.append(kw("MORead"))
    return out + [KEYWORDS[k] for k in h.keywords]


def compact_bang(text):
    lines = text.splitlines()
    bang = [l[1:].strip() for l in lines if l.startswith("!")]
    rest = [l for l in lines if not l.startswith("!")]
    return "\n".join(["! " + " ".join(bang), *rest]) if bang else text


@functools.cache
def with_raw(cls):                   # verbatim lines before "end": the only way to get nested sub-blocks (PTSettings ... end)
    class Raw(cls):
        _raw: str = PrivateAttr("")

        def format_orca(self):
            s = super().format_orca()
            return s[:-3] + self._raw + "\nend" if self._raw else s

    Raw.__name__ = cls.__name__
    return Raw


def to_opi_block(b):
    if isinstance(b, CasscfBlock):
        cls, name = BlockCasscf, "casscf"
        data = {**b.model_dump(exclude={"kind", "extra", "raw"}, exclude_none=True), **b.extra}
    else:
        cls, name, data = BLOCKS[b.name], b.name, dict(b.settings)
    unknown = set(data) - set(cls.model_fields)
    if unknown:
        raise ValueError(f"%{name} does not accept {sorted(unknown)}; known settings include "
                         f"{sorted(f for f in cls.model_fields if not f.startswith('_'))[:20]}")
    if not b.raw:
        return cls(**data)
    blk = with_raw(cls)(**data)
    blk._raw = b.raw
    return blk


AUX_FIELD = {"/JK": "newauxjkgto", "/J": "newauxjgto", "/C": "newauxcgto"}   # /JK before /J


def basis_block(b):
    fields = {}
    for el, bs in b.per_element.items():
        fields["newgto"] = NewBasis(element=el, basis=sk.SimpleKeyword(bs))
    for el, bs in b.per_element_aux.items():
        field = next((f for suf, f in AUX_FIELD.items() if bs.upper().endswith(suf)), "newauxgto")
        fields[field] = NewBasis(element=el, basis=sk.SimpleKeyword(bs))
    return BlockBasis(**fields) if fields else None


# ---- molecule -----------------------------------------------------------
def structure(m, strict=False):
    if m.xyzfile:
        return XyzFile(m.xyzfile, charge=m.charge, multiplicity=m.mult, strict=strict)
    lines = [l for l in m.xyz.strip().splitlines() if l.strip()]
    block = "\n".join([str(len(lines)), "", *lines])
    mol = Structure.from_xyz_block(block, charge=m.charge, multiplicity=m.mult)
    if not mol.multiplicity_is_possible:
        raise ValueError(f"multiplicity {m.mult} is impossible for {mol.nelectrons} electrons")
    return mol


# ---- assembly -----------------------------------------------------------
def to_opi_input(inp: OrcaInput) -> Input:
    oi = Input()
    oi.ncores, oi.memory = inp.resources.nprocs, inp.resources.maxcore
    if inp.directives.base:                       # %base / %moinp as OPI arbitrary strings at the top:
        oi.add_arbitrary_string(f'%base "{inp.directives.base}"', pos="top")
    if inp.directives.moinp:                      # Input.moinp would demand the .gbw to exist; we only write inputs here
        oi.add_arbitrary_string(f'%moinp "{inp.directives.moinp}"', pos="top")
    oi.add_simple_keywords(*bang_keywords(inp.header, moread=bool(inp.directives.moinp)))
    blocks = [to_opi_block(b) for b in inp.blocks]
    if (bb := basis_block(inp.header.basis)):
        blocks.append(bb)
    oi.add_blocks(*blocks)
    return oi


def render(inp: OrcaInput, working_dir=".", strict=False) -> str:
    wd = Path(working_dir).resolve()
    oi, mol = to_opi_input(inp), structure(inp.molecule, strict=strict)
    coords = mol.format_orca(wd) if isinstance(mol, BaseStructureFile) else mol.format_orca()
    parts = [oi.format_before_coords(wd), coords, oi.format_after_coords()]
    return compact_bang("\n".join(p for p in parts if p))
