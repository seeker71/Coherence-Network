
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from app.services.slot_selection_service import SlotSelector

def test_slot_selector_basic_selection(tmp_path):
    store_path = tmp_path / "test_selector.json"
    selector = SlotSelector("test", store_path=store_path)
    
    # Empty store -> uniform random
    slots = ["a", "b", "c"]
    selection = selector.select(slots)
    assert selection in slots

def test_slot_selector_convergence(tmp_path):
    """Arm A is 100% successful, Arm B is 0% successful. Should converge to A."""
    store_path = tmp_path / "convergence.json"
    selector = SlotSelector("test", store_path=store_path)
    slots = ["A", "B"]
    
    # Record 10 successes for A
    for _ in range(10):
        selector.record("A", value_score=1.0, resource_cost=1.0)
    
    # Record 10 failures for B
    for _ in range(10):
        selector.record("B", value_score=0.0, resource_cost=1.0)
        
    # Over 100 selections, A should be picked almost every time (TS exploitation)
    selections = [selector.select(slots) for _ in range(100)]
    a_count = selections.count("A")
    assert a_count > 95

def test_slot_selector_recency_shift(tmp_path):
    """Arm A was good but now fails. System should shift to B."""
    store_path = tmp_path / "recency.json"
    selector = SlotSelector("test", store_path=store_path)
    slots = ["A", "B"]
    
    # A was good (20 successes)
    for _ in range(20):
        selector.record("A", value_score=1.0, resource_cost=1.0)
    
    # B is mediocre (10 successes, 10 failures)
    for _ in range(10):
        selector.record("B", value_score=1.0, resource_cost=1.0)
        selector.record("B", value_score=0.0, resource_cost=1.0)
        
    # Initially A is preferred
    assert selector.select(slots) == "A"
    
    # Now A fails 5 times in a row (recent failure)
    for _ in range(5):
        selector.record("A", value_score=0.0, resource_cost=1.0)
        
    # System should now be more likely to pick B because A's recent rate dropped to 0
    # Over 50 selections, B should get a significant share or even dominant
    selections = [selector.select(slots) for _ in range(50)]
    b_count = selections.count("B")
    assert b_count > 25  # B should be preferred or at least very competitive now

def test_slot_selector_blocked_behavior(tmp_path):
    """All slots failed 3 times -> all blocked. Should still pick one (probe)."""
    store_path = tmp_path / "blocked.json"
    selector = SlotSelector("test", store_path=store_path)
    slots = ["A", "B"]
    
    for _ in range(3):
        selector.record("A", value_score=0.0, resource_cost=1.0)
        selector.record("B", value_score=0.0, resource_cost=1.0)
        
    # Both blocked
    st = selector.stats(slots)
    assert st["slots"]["A"]["blocked"] is True
    assert st["slots"]["B"]["blocked"] is True
    
    # select() should still return one of them (not None)
    selection = selector.select(slots)
    assert selection in slots

def test_slot_selector_versioning(tmp_path):
    """Measurements for old versions should be ignored."""
    store_path = tmp_path / "versioning.json"
    selector = SlotSelector("test", store_path=store_path)
    slots = ["A"]
    
    # Version 1 was perfect
    for _ in range(10):
        selector.record("A", value_score=1.0, resource_cost=1.0, config_version="v1")
        
    # Current version is v2. No measurements yet.
    # If we pass version_map={"A": "v2"}, it should ignore v1 data and be uniform (random sample from Beta(1,1))
    # Since we only have one slot, it will pick A, but stats should show 0 samples.
    st = selector.stats(slots, version_map={"A": "v2"})
    assert st["slots"]["A"]["sample_count"] == 0
    
def test_slot_selector_cooldown(tmp_path):
    """Blocked slot should unblock after cooldown."""
    store_path = tmp_path / "cooldown.json"
    selector = SlotSelector("test", store_path=store_path)
    
    # Fail 3 times
    now = datetime.now(timezone.utc)
    for i in range(3):
        selector.record("A", value_score=0.0, resource_cost=1.0)
    
    assert SlotSelector._is_blocked(selector._load_measurements()) is True
    
    # Mock records with old timestamp
    old_time = now - timedelta(hours=2)
    measurements = selector._load_measurements()
    for m in measurements:
        m["timestamp"] = old_time.isoformat()
        
    with open(store_path, "w") as f:
        json.dump(measurements, f)
        
    # Should no longer be blocked because 2 hours > 1 hour cooldown
    assert SlotSelector._is_blocked(selector._load_measurements()) is False
