from pydantic import Field, model_validator, field_validator
from .base import SchemaModel

class Molecule(SchemaModel):
    """
    Molecule specification for ORCA
    """
    charge: int = 0
    mult: int = Field(1, ge=1, description=" spin multiplicity (2S+1)")
    xyzfile: str | None = Field(None, description="the structure file name as given in the request, with or without extension (e.g. 'structure', 'h2o.xyz')")
    xyz: str | None = Field(None, description="only when the request contains coordinates; otherwise use xyzfile" )

    @model_validator(mode="after")
    def one_geometry(self):
        if not (self.xyzfile or self.xyz):
            raise ValueError("no geometry: set xyzfile to the structure file named in the request, or xyz to the coordinates given in the request")
        if self.xyzfile and self.xyz:
            raise ValueError(f"xyzfile {self.xyzfile!r} is given: remove xyz, coordinates come from the file")
        return self

    @field_validator("xyz")
    @classmethod
    def atom_lines(cls, v):
        if v is None:
            return v
        lines = [l.strip() for l in v.splitlines()
                 if l.strip() and not l.strip().startswith("*") and len(l.split()) != 1]   # drop "* xyz 0 1", "*", atom count
        for line in lines:
            tok = line.split()
            if len(tok) != 4 or not tok[0].isalpha():
                raise ValueError(f"xyz line {line!r} is not 'Element x y z'; give one atom per line with Cartesian coordinates, "
                                 "no charge/multiplicity or atom-count lines, no Z-matrix")
            float(tok[1]), float(tok[2]), float(tok[3])
        return "\n".join(lines) or None
    