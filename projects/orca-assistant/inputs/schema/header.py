from pydantic import Field, field_validator, model_validator
from .base import SchemaModel
from .basis import Basis
from .vocab import Task, OptConv, ScfConv, ShellType, METHODS, KEYWORDS, is_composite, resolve, norm

FAMILIES = {"dft": "give the functional named in the request (m062x, b3lyp, pbe0, ...)",
            "wft": "give the wavefunction method (hf, mp2, ccsd(t), casscf, ...)",
            "abinitio": "give the wavefunction method (hf, mp2, ccsd(t), casscf, ...)"}

TASK_ALIASES = {"sp": "SP", "singlepoint": "SP", "energy": "SP", "opt": "Opt", "optts": "OptTS",
                "freq": "Freq", "numfreq": "NumFreq", "numgrad": "NumGrad"}


class Header(SchemaModel):
    method: str = Field(description="the method named in the request, in ORCA spelling: hf, b3lyp, m062x, r2scan3c, casscf, dlpno-ccsd(t), ...; "
                                    "for DFT give the functional, never the word DFT")
    basis: Basis = Field(default_factory=Basis)
    tasks: list[Task] = Field(default_factory=lambda: ["SP"],
                              description="Opt for geometry optimisation, Freq for frequencies, SP for single point; several allowed, e.g. ['Opt', 'Freq']")
    opt_convergence: OptConv | None = Field(None, description="geometry convergence ('tight optimisation' -> 'Tight'); only with Opt")
    scf_convergence: ScfConv | None = Field(None, description="SCF convergence level: 'tight SCF' in the request means 'Tight' here, never in keywords")
    shell: ShellType | None = Field(None, description="'unrestricted' for unrestricted/open-shell (UKS/UHF), 'restricted-open-shell' for ROKS/ROHF, "
                                                      "'closed-shell' only if the request insists; the KS/HF letters are derived from the method")
    keywords: list[str] = Field(default_factory=list,
                                description="other ! flags explicitly requested (RIJCOSX, D4, UNO, ...); never the method, basis, tasks or convergence")

    @field_validator("tasks", mode="before")
    @classmethod
    def canonical_tasks(cls, v):
        return [TASK_ALIASES.get(str(t).lower(), t) for t in v]

    @field_validator("keywords", mode="before")
    @classmethod
    def canonical_keywords(cls, v):
        return [resolve(KEYWORDS, str(k).lstrip("! ").strip(), "keyword") for k in v]

    @field_validator("method", mode="before")
    @classmethod
    def canonical_method(cls, v):
        if (hint := FAMILIES.get(norm(v).replace(" ", ""))):
            raise ValueError(f"{v!r} is a family of methods, not a method; {hint}")
        return resolve(METHODS, v, "method")

    @model_validator(mode="before")
    @classmethod
    def drop_shell_for_casscf(cls, d):            # shell is meaningless for casscf: drop, don't reject
        if isinstance(d, dict) and norm(d.get("method", "")) == "casscf":
            d = {k: v for k, v in d.items() if k != "shell"}
        return d

    @model_validator(mode="after")
    def consistent(self):
        if not self.tasks:
            raise ValueError("tasks cannot be empty; use ['SP'] for a single point")
        if "SP" in self.tasks and len(self.tasks) > 1:
            raise ValueError("SP cannot be combined with other tasks; drop 'SP' and keep the others")
        if self.opt_convergence and "Opt" not in self.tasks:
            raise ValueError("opt_convergence is set but 'Opt' is not in tasks; add 'Opt' to tasks or unset opt_convergence")
        if is_composite(self.method) and self.basis.main:
            raise ValueError(f"{self.method} is a composite method that includes its basis; unset basis.main")
        if not is_composite(self.method) and not self.basis.main:
            raise ValueError("basis.main is required for this method; set it to the basis named in the request")
        b = self.basis
        for k in self.keywords:
            if k in METHODS or k == b.main or k in b.aux:
                raise ValueError(f"keyword {k!r} duplicates header.method or header.basis; remove it from keywords")
        return self


class Directives(SchemaModel):
    base: str | None = Field(None, description="output file base name, if the request names one")
    moinp: str | None = Field(None, description="gbw file to read orbitals from (inside the working directory); MORead is added automatically")

    @field_validator("moinp")
    @classmethod
    def gbw_only(cls, v):
        if v is not None and not v.lower().endswith(".gbw"):
            raise ValueError(f"moinp {v!r} is not a .gbw file; moinp only reads orbitals from a file the request "
                            "names. Orbital flags (UNO, ...) go in header.keywords")
        return v


class Resources(SchemaModel):
    nprocs: int = Field(1, ge=1, description="number of processors/cores requested")
    maxcore: int = Field(2000, ge=100, description="memory per core in MB")
