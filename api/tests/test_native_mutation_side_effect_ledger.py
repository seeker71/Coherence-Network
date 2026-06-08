"""Proof that native mutation side effects are source-classified, not circular."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = ROOT / "docs" / "coherence-substrate" / "native-mutation-side-effect-ledger.form"
IDEAS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "ideas-router.form"
SPECS_FORM_PATH = ROOT / "docs" / "coherence-substrate" / "spec-registry-router.form"
SIDE_EFFECTS_SPEC_PATH = ROOT / "specs" / "native-mutation-side-effects.md"
ROUTE_BINDING_SPEC_PATH = ROOT / "specs" / "native-mutation-route-side-effect-binding.md"
PUBLIC_GATE_SPEC_PATH = ROOT / "specs" / "native-mutation-public-gate.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _entry(text: str, effect_id: str) -> str:
    pattern = rf'nmsl_entry\(\s*"{re.escape(effect_id)}".*?\n\s*\)'
    match = re.search(pattern, text, flags=re.DOTALL)
    assert match, f"missing ledger entry {effect_id}"
    return match.group(0)


def test_ledger_declares_anti_circular_decision_rule():
    text = _text(LEDGER_PATH)

    for required in (
        "defn native_mutation_side_effect_ledger()",
        "anti_circular_rule",
        "Side effects are not justified by side-effect proof.",
        "A parity effect must cite existing Python behavior.",
        "A gate receipt may have no Python source only when it is reversible gate safety.",
        "unjustified_additions: 0",
        "defn native_mutation_side_effect_recipe_shift()",
    ):
        assert required in text


def test_python_parity_entries_cite_python_sources_and_form_carriers():
    text = _text(LEDGER_PATH)

    expected = {
        "idea-parent-edge-repair": (
            "python_parity_effect",
            "api/app/routers/ideas.py::create_idea",
            "api/app/services/idea_hierarchy.py::set_parent_idea",
            "form/form-stdlib/native-mutation-side-effects.fk::nms-repair-parent-edge",
        ),
        "spec-delete-edge-cleanup": (
            "python_parity_effect",
            "api/app/services/graph_service.py::delete_node",
            "form/form-stdlib/application-graph-node-port.fk::agn-delete-node",
        ),
        "cache-invalidation-receipt": (
            "python_parity_effect",
            "api/app/services/idea_service.py::_invalidate_ideas_cache",
            "api/app/services/spec_registry_service.py::_invalidate_spec_cache",
            "form/form-stdlib/native-mutation-side-effects.fk::nms-record-cache-invalidation",
        ),
        "contributor-key-audit": (
            "python_parity_effect",
            "api/app/services/contributor_key_store.py::verify",
            "form/form-stdlib/native-mutation-side-effects.fk::nms-audit-contributor-key",
        ),
        "idea-valuation-audit-ledger": (
            "python_parity_effect",
            "api/app/services/idea_write_ops.py::update_idea",
            "api/app/services/idea_write_ops.py::update_ideas_batch",
            "api/app/services/audit_ledger_service.py::append_entry",
            "form/form-stdlib/native-idea-valuation-audit-ledger.fk::nival-record-valuation-change",
        ),
    }

    for effect_id, required_parts in expected.items():
        entry = _entry(text, effect_id)
        for required in required_parts:
            assert required in entry


def test_gate_receipts_are_not_claimed_as_python_parity():
    text = _text(LEDGER_PATH)

    for effect_id in ("rollback-receipt", "public-gate-rollback-receipt"):
        entry = _entry(text, effect_id)
        assert '"gate_receipt"' in entry
        assert "none: reversible gate evidence, not Python parity" in entry
        assert "do not cite as domain parity" in entry
        assert '"python_parity_effect"' not in entry

    assert "receipt is side-effect evidence for rollback discipline, not a reason to add domain side effects" in text


def test_audit_ledger_parity_is_carried_before_ordinary_flip():
    text = _text(LEDGER_PATH)
    entry = _entry(text, "idea-valuation-audit-ledger")

    for required in (
        '"python_parity_effect"',
        "api/app/services/idea_write_ops.py::update_idea",
        "api/app/services/idea_write_ops.py::update_ideas_batch",
        "api/app/services/audit_ledger_service.py::append_entry",
        "form/form-stdlib/native-idea-valuation-audit-ledger.fk::nival-run-idea-update-with-valuation-audit",
        "form/scripts/native-idea-valuation-audit-ledger-test.sh",
        "idea valuation audit-ledger parity is carried Form-native",
    ):
        assert required in entry or required in text
    assert "missing_python_parity: 0" in text
    assert "carry idea-valuation-audit-ledger Form-native or retire it by explicit spec" not in text


def test_route_forms_and_specs_link_the_ledger_boundary():
    for text in (_text(IDEAS_FORM_PATH), _text(SPECS_FORM_PATH)):
        assert "docs/coherence-substrate/native-mutation-side-effect-ledger.form" in text
        assert "source-classified side-effect ledger" in text
        assert "rollback receipts are reversible gate safety, not Python parity" in text
        assert "idea-valuation-audit-ledger is now carried Form-native" in text
        assert "native idea valuation audit ledger proven" in text

    for text in (
        _text(SIDE_EFFECTS_SPEC_PATH),
        _text(ROUTE_BINDING_SPEC_PATH),
        _text(PUBLIC_GATE_SPEC_PATH),
    ):
        assert "native-mutation-side-effect-ledger.form" in text
        assert "side-effect proof does not justify side effects" in text
        assert "rollback receipts are gate-local safety rather than Python parity" in text
