"""Tests for Transparent Audit Ledger -- spec 123."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.models.audit_ledger import AuditEntryType, AuditEntryCreate
from app.services import audit_ledger_service, unified_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    unified_db.ensure_schema()
    # Clear ledger for each test
    with unified_db.session() as session:
        from app.services.audit_ledger_service import AuditEntryRecord, AuditSnapshotRecord
        session.query(AuditEntryRecord).delete()
        session.query(AuditSnapshotRecord).delete()
        session.commit()

def test_append_and_verify_ledger():
    # 1. Append entries
    entry1 = audit_ledger_service.append_entry(
        AuditEntryCreate(
            entry_type=AuditEntryType.CC_MINTED,
            sender_id="SYSTEM",
            receiver_id="user_1",
            amount_cc=100.0,
            reason="Initial mint",
        )
    )
    
    entry2 = audit_ledger_service.append_entry(
        AuditEntryCreate(
            entry_type=AuditEntryType.CC_TRANSFER,
            sender_id="user_1",
            receiver_id="user_2",
            amount_cc=50.0,
            reason="Payment",
            reference_id="tx_123",
        )
    )
    
    assert entry1.entry_id == "aud_00001"
    assert entry2.entry_id == "aud_00002"
    assert entry2.previous_hash == entry1.hash
    
    # 2. Verify chain
    res = audit_ledger_service.verify_chain()
    assert res.verified is True
    assert res.entries_checked == 2
    assert res.computed_head_hash == entry2.hash

def test_tamper_detection():
    # 1. Append entry
    entry = audit_ledger_service.append_entry(
        AuditEntryCreate(
            entry_type=AuditEntryType.CC_MINTED,
            sender_id="SYSTEM",
            receiver_id="user_1",
            amount_cc=100.0,
            reason="Initial mint",
        )
    )
    
    # 2. Tamper with DB directly
    with unified_db.session() as session:
        from app.services.audit_ledger_service import AuditEntryRecord
        record = session.query(AuditEntryRecord).first()
        record.amount_cc = 999.0 # Tamper!
        session.commit()
        
    # 3. Verify should fail
    res = audit_ledger_service.verify_chain()
    assert res.verified is False
    assert res.first_invalid_entry_id == "aud_00001"

def test_audit_api_endpoints():
    # 1. Create data
    audit_ledger_service.append_entry(
        AuditEntryCreate(
            entry_type=AuditEntryType.CC_MINTED,
            sender_id="SYSTEM",
            receiver_id="user_1",
            amount_cc=100.0,
            reason="Mint",
        )
    )
    
    # 2. Query transactions
    response = client.get("/api/audit/transactions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["entries"][0]["entry_type"] == "CC_MINTED"
    
    # 3. Verify via API
    response = client.get("/api/audit/verify")
    assert response.status_code == 200
    assert response.json()["verified"] is True

def test_governance_integration():
    from app.models.governance import ChangeRequestCreate, ChangeRequestType, ChangeRequestVoteCreate, VoteDecision, ChangeRequestVote
    from app.services import governance_service
    
    # 1. Create CR
    cr = governance_service.create_change_request(
        ChangeRequestCreate(
            request_type=ChangeRequestType.IDEA_CREATE,
            title="Test Idea",
            payload={"id": "test-idea", "name": "Test", "description": "Desc", "potential_value": 10.0, "estimated_cost": 5.0},
            proposer_id="user_1",
            proposer_type="human",
        )
    )
    
    # 2. Vote
    governance_service.cast_vote(
        cr.id,
        ChangeRequestVoteCreate(
            voter_id="user_2",
            voter_type="human",
            decision=VoteDecision.YES,
            rationale="Good idea",
        )
    )
    
    # 3. Check audit ledger via API
    response = client.get("/api/audit/governance")
    assert response.status_code == 200
    data = response.json()
    # Should have 2 entries: VOTE and DECISION (since 1 vote is enough for default)
    assert data["total"] >= 2
    types = [e["entry_type"] for e in data["entries"]]
    assert "GOVERNANCE_VOTE" in types
    assert "GOVERNANCE_DECISION" in types

def test_valuation_integration():
    from app.services import idea_service
    from app.models.idea import IdeaCreate
    
    # 1. Create idea
    idea_service.create_idea(
        idea_id="audit-test-idea",
        name="Test",
        description="Desc",
        potential_value=10.0,
        estimated_cost=5.0,
    )
    
    # 2. Update valuation
    idea_service.update_idea("audit-test-idea", actual_value=5.0)
    
    # 3. Check audit ledger
    response = client.get("/api/audit/transactions?entry_type=VALUATION_CHANGE")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["entries"][0]["entry_type"] == "VALUATION_CHANGE"
    assert data["entries"][0]["metadata"]["field"] == "actual_value"
    assert data["entries"][0]["metadata"]["new_value"] == 5.0
