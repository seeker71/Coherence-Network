"""Centered discernment Form practice creates cells, recipes, and ledger entries."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import lookup_cell
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.substrate_strings import SubstrateStringORM


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "substrate_centered_discernment_practice.py"
)


@pytest.fixture
def session():
    """In-memory SQLite session with substrate tables only."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


def _load_practice_module():
    spec = importlib.util.spec_from_file_location("centered_practice", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_centered_discernment_practice_records_substrate_lifecycle(session, tmp_path):
    module = _load_practice_module()
    ledger = tmp_path / "ledger.jsonl"

    result = module.execute_practice(
        session,
        timestamp="2026-05-18T08:00:00+08:00",
        ledger_path=ledger,
    )

    assert result["form_source"].startswith("do {")
    assert result["form_value"] == (
        "youtube_testimony_stream_received -> "
        "centered_felt_sense_has_precedence -> "
        "testimony_carries_most_valuable_evidence -> "
        "direct_perception_leads_the_summary -> "
        "context_enters_as_companion -> "
        "curiosity_opens_shared_worlds -> "
        "form_transmutes_stream_into_cells"
    )
    assert result["practice_recipe"].level >= 3

    life_agent = lookup_cell(session, "presence", "life-sub-agent")
    task = lookup_cell(session, "task", "centered-discernment-practice")
    assert life_agent is not None
    assert task is not None
    assert life_agent.blueprint == result["named_cells"]["life_sub_agent"]["blueprint"]
    assert task.ctor == result["named_cells"]["practice_task"]["ctor"]

    witnesses = result["named_cells"]["witnesses"]
    assert len(witnesses) == 7
    for witness in witnesses:
        assert lookup_cell(session, "witness", witness["name"]) is not None
        assert witness["blueprint"] is not None
        assert witness["ctor"] is not None

    entries = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [entry["kind"] for entry in entries] == [
        "form_recipe",
        "cell",
        "cell",
        "witness",
        "witness",
        "witness",
        "witness",
        "witness",
        "witness",
        "witness",
        "completion",
    ]
    assert entries[0]["recipe"].startswith("@")
    assert entries[-1]["practice_recipe"].startswith("@")
    assert entries[0]["source_url"].startswith("https://youtu.be/KFaU6qR_iPg")
    assert entries[-1]["named_cell_count"] == 9
