import difflib
from typing import Literal

from opi.input import blocks as opi_blocks, simple_keywords as sk
from opi.input.blocks import BlockCasscf

Task = Literal["SP", "Opt", "OptTS", "Freq", "NumFreq", "NumGrad"]
OptConv = Literal["Loose", "Normal", "Tight", "VeryTight"]
ScfConv = Literal["Sloppy", "Loose", "Normal", "Strong", "Tight", "VeryTight"]
ShellType = Literal["closed-shell", "unrestricted", "restricted-open-shell"]
PTMethod = BlockCasscf.model_fields["ptmethod"].annotation.__args__[0]   # OPI's Literal, without the Optional
Scalar = str | int | float | bool

# ---- OPI is the catalogue: tables and Literals built from the installed OPI ----
BLOCKS = {n[5:].lower(): getattr(opi_blocks, n)
          for n in dir(opi_blocks) if n.startswith("Block") and n != "Block"}
BlockName = Literal[tuple(sorted(BLOCKS))]

# setting-level: a key that belongs to a header/resources field
OWNED = {("method", "runtyp"): "header.tasks (Opt, Freq, SP)",
         ("pal", "nprocs"): "resources.nprocs",
         ("method", "maxcore"): "resources.maxcore",
         ("scf", "convergence"): "header.scf_convergence",
         ("geom", "convergence"): "header.opt_convergence"}

# block-level: where the things people put in this block usually belong
HINTS = {"basis": "per-element bases go in header.basis.per_element / per_element_aux; "
                  "the main and auxiliary bases in header.basis.main / header.basis.aux",
         "pal": "cores go in resources.nprocs; no %pal block is needed",
         "method": "the method goes in header.method, the run type in header.tasks",
         "freq": "frequencies are requested with 'Freq' in header.tasks; use %freq only for its own settings (temp, scalfreq, ...)",
         "geom": "an optimisation is requested with 'Opt' in header.tasks; use %geom only for its own settings (maxiter, constraints, ...)"}


def norm(name):                      # one spelling rule: M06-2X, m062x, M06_2X -> m062x
    return str(name).lower().replace("-", "").replace("_", "").replace("/", "")


def _box(cls):
    return {v.keyword: v for n in dir(cls)
            if not n.startswith("_") and hasattr((v := getattr(cls, n)), "keyword")}


METHODS = {k: v for box in (sk.Dft, sk.Wft, sk.Method, sk.Sqm) for k, v in _box(box).items()}
METHODS["casscf"] = sk.ShellType.CASSCF          # OPI files it with the shell types; for us it is the method
DFT_METHODS = _box(sk.Dft)                       # decides KS vs HF in shell_keyword
AUX_BASES = _box(sk.AuxBasisSet)
BASES = _box(sk.BasisSet)
KEYWORDS = {k: v for box in vars(sk).values()
            if isinstance(box, type) and issubclass(box, sk.SimpleKeywordBox) and box is not sk.SimpleKeywordBox
            for k, v in _box(box).items()}



COMPOSITE_SUFFIXES = ("3c", "xtb")   # methods that carry their own basis



def canonical(table, name):
    """Map any spelling to the catalogue's key, or return the input unchanged (the Literal then rejects it)."""
    by_norm = {norm(k): k for k in table}
    return by_norm.get(norm(name), name)


def suggest(table, name, n=3):
    by_norm = {norm(k): k for k in table}
    return [by_norm[m] for m in difflib.get_close_matches(norm(name), by_norm, n=n)]


def is_composite(method):
    return norm(method).endswith(COMPOSITE_SUFFIXES)


def shell_keyword(method, shell):   # concept -> ORCA keyword: unrestricted + m062x -> UKS, + ccsd -> UHF
    prefix = {"closed-shell": "R", "unrestricted": "U", "restricted-open-shell": "RO"}[shell]
    return prefix + ("KS" if method in DFT_METHODS else "HF")


def resolve(table, name, what):
    key = canonical(table, name)
    if key in table:
        return key
    hint = suggest(table, name)
    raise ValueError(f"unknown {what} {name!r}" + (f"; did you mean {hint}?" if hint else ""))