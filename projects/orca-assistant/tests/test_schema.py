import copy
import json
import pytest
from pydantic import ValidationError
from inputs.schema import OrcaInput

EXAMPLE_FILE = json.loads(open("data/examples/eve_s9t9.json").read())


def test_validates():
    assert OrcaInput.model_validate(EXAMPLE_FILE).block("casscf").nel == 14


def test_rejects_invalid_electrons():
    data = copy.deepcopy(EXAMPLE_FILE)
    data["blocks"][0]["nel"] = 30  # electrons > 2*norb
    with pytest.raises(ValidationError):
        OrcaInput.model_validate(data)


def test_rejects_opt_convergence_without_opt():
    data = copy.deepcopy(EXAMPLE_FILE)
    data["header"]["opt_convergence"] = "Tight"
    with pytest.raises(ValidationError):
        OrcaInput.model_validate(data)


def test_rejects_unknown_field():
    data = copy.deepcopy(EXAMPLE_FILE)
    data["blocks"][0]["nevpt2"] = True
    with pytest.raises(ValidationError):
        OrcaInput.model_validate(data)


def test_energy_alias_becomes_sp():
    data = copy.deepcopy(EXAMPLE_FILE)
    data["header"]["tasks"] = ["Energy"]
    inp = OrcaInput.model_validate(data)
    assert inp.header.tasks == ["SP"]

# ---- catalogue: the tables are only as good as the introspection that builds them
@pytest.mark.parametrize("table,key", [
    ("METHODS", "casscf"), ("METHODS", "dlpno-ccsd(t)"), ("METHODS", "dlpno-mp2"), ("METHODS", "m062x"),
    ("KEYWORDS", "uks"), ("KEYWORDS", "moread"), ("KEYWORDS", "scnl"), ("AUX_BASES", "def2-tzvp/c"),
])
def test_catalogue_has(table, key):
    from inputs.schema import vocab
    assert key in getattr(vocab, table)


def header(**kw):
    base = {"method": "m062x", "basis": {"main": "def2-SVP"}}
    return OrcaInput.model_validate({"header": {**base, **kw}, "molecule": {"xyzfile": "a.xyz"}}).header


def test_method_spellings_resolve():
    assert header(method="M06-2X").method == "m062x"
    assert header(method="DLPNO-CCSD(T)").method == "dlpno-ccsd(t)"


def test_family_word_is_routed():
    with pytest.raises(ValidationError, match="family of methods"):
        header(method="DFT")


def test_shell_is_a_concept():
    from inputs.schema.vocab import shell_keyword
    assert shell_keyword("m062x", "unrestricted") == "UKS"
    assert shell_keyword("ccsd(t)", "unrestricted") == "UHF"
    assert shell_keyword("b3lyp", "restricted-open-shell") == "ROKS"
    # casscf: shell is dropped silently (tested in test_casscf_in_generic_spelling)


def test_per_element_repairs_and_routes():
    b = header(basis={"main": "def2-SVP", "aux": ["def2/J", "def2-SVP/C", "def2-TZVP/C"],
                      "per_element": {"zn": "def2-TZVP"}, "per_element_aux": {"Zn": "def2-TZVP/C"}}).basis
    assert b.aux == ["def2/j", "def2-svp/c"]            # Zn's /C taken as per-element, not a conflict
    assert b.per_element == {"Zn": "def2-TZVP"}         # element symbol canonicalised
    assert header(basis={"main": "def2-SVP", "per_element": {"O": "def2-SVP"}}).basis.per_element == {}   # same as main: noise
    with pytest.raises(ValidationError, match="not an element symbol"):
        header(basis={"main": "def2-SVP", "per_element": {"all": "def2-TZVP"}})


def test_moinp_must_be_gbw():
    with pytest.raises(ValidationError, match="not a .gbw"):
        OrcaInput.model_validate({"header": {"method": "hf", "basis": {"main": "def2-SVP"}},
                                  "molecule": {"xyzfile": "a.xyz"}, "directives": {"moinp": "QROA"}})


def test_misplaced_settings_are_moved():
    inp = OrcaInput.model_validate({
        "header": {"method": "pbe0", "basis": {"main": "def2-TZVP"}},
        "molecule": {"xyz": "* xyz 0 1\nO 0.0 0.0 0.0\nH 0.96 0.0 0.0\nH -0.24 0.94 0.0\n*"},
        "blocks": [{"name": "scf", "settings": {"convergence": "verytight", "charge": 1, "mult": 2}}]})
    assert inp.header.scf_convergence == "VeryTight"
    assert (inp.molecule.charge, inp.molecule.mult) == (1, 2)
    assert inp.blocks == []                                   # emptied block removed
    assert inp.molecule.xyz.splitlines()[0].startswith("O ")  # framing lines stripped


def test_comma_lists_in_casscf():
    inp = OrcaInput.model_validate({
        "header": {"method": "casscf", "basis": {"main": "def2-SVP"}}, "molecule": {"xyzfile": "a.xyz"},
        "blocks": [{"kind": "casscf", "nel": 8, "norb": 8, "mult": "1,3", "nroots": "2,3"}]})
    assert (inp.blocks[0].mult, inp.blocks[0].nroots) == ([1, 3], [2, 3])


def test_casscf_in_generic_spelling():
    inp = OrcaInput.model_validate({
        "header": {"method": "casscf", "basis": {"main": "def2-TZVP"}, "shell": "closed-shell"},
        "molecule": {"xyzfile": "a.xyz"},
        "blocks": [{"name": "casscf", "settings": {"nel": 10, "norb": 10, "nroots": 7, "DoNTO": True, "ptmethod": "SC-NEVPT2"},
                    "raw": "DoNDO true"}]})
    b = inp.blocks[0]
    assert (b.kind, b.nel, b.nroots, b.ptmethod, b.extra, b.raw) == ("casscf", 10, 7, "sc_nevpt2", {"donto": True}, "DoNDO true")
    assert inp.header.shell is None                          # dropped, not rejected
    with pytest.raises(ValidationError, match="sc_nevpt2 or fic_nevpt2"):
        OrcaInput.model_validate({"header": {"method": "casscf", "basis": {"main": "def2-SVP"}}, "molecule": {"xyzfile": "a.xyz"},
                                  "blocks": [{"kind": "casscf", "nel": 2, "norb": 2, "ptmethod": "NEVPT2"}]})


def test_generic_keys_lowercased_and_raw_allowed():
    inp = OrcaInput.model_validate({"header": {"method": "bhandhlyp", "basis": {"main": "def2-TZVP"}}, "molecule": {"xyzfile": "a.xyz"},
                                    "blocks": [{"name": "tddft", "settings": {"Nroots": 5}, "raw": "sf true"}]})
    assert inp.blocks[0].settings == {"nroots": 5}


def test_basis_block_moves_into_header():
    inp = OrcaInput.model_validate({
        "header": {"method": "m062x", "basis": {"main": "def2-SVP", "per_element": {"Zn": "def2-TZVP"}}},
        "molecule": {"xyzfile": "a.xyz"},
        "blocks": [{"name": "basis", "settings": {"AuxJ": "def2/J", "AuxC": "def2-SVP/C"}}]})
    assert inp.header.basis.aux == ["def2/j", "def2-svp/c"] and inp.blocks == []


def test_two_casscf_blocks_are_routed():
    with pytest.raises(ValidationError, match="one casscf block with"):
        OrcaInput.model_validate({"header": {"method": "casscf", "basis": {"main": "def2-SVP"}}, "molecule": {"xyzfile": "a.xyz"},
                                  "blocks": [{"kind": "casscf", "nel": 8, "norb": 8, "mult": 1}, {"kind": "casscf", "nel": 8, "norb": 8, "mult": 3}]})
