"""Tests for the 5 concrete service contracts."""

import pytest

from app.services.service_contract import ServiceSpec
from app.services.contracts.idea_contract import IdeaServiceContract
from app.services.contracts.agent_contract import AgentServiceContract
from app.services.contracts.runtime_contract import RuntimeServiceContract
from app.services.contracts.inventory_contract import InventoryServiceContract
from app.services.contracts.federation_contract import FederationServiceContract


# -- Idea --

def test_idea_contract_spec():
    contract = IdeaServiceContract()
    spec = contract.get_service_spec()
    assert isinstance(spec, ServiceSpec)
    assert spec.id == "coherence.idea"
    assert len(spec.capabilities) > 0


def test_idea_contract_health_check():
    contract = IdeaServiceContract()
    result = contract.health_check()
    assert isinstance(result, dict)


# -- Agent --

def test_agent_contract_spec():
    contract = AgentServiceContract()
    spec = contract.get_service_spec()
    assert isinstance(spec, ServiceSpec)
    assert spec.id == "coherence.agent"
    assert len(spec.capabilities) > 0


def test_agent_contract_health_check():
    contract = AgentServiceContract()
    result = contract.health_check()
    assert isinstance(result, dict)


# -- Runtime --

def test_runtime_contract_spec():
    contract = RuntimeServiceContract()
    spec = contract.get_service_spec()
    assert isinstance(spec, ServiceSpec)
    assert spec.id == "coherence.runtime"
    assert len(spec.capabilities) > 0


def test_runtime_contract_health_check():
    contract = RuntimeServiceContract()
    result = contract.health_check()
    assert isinstance(result, dict)


# -- Inventory --

def test_inventory_contract_spec():
    contract = InventoryServiceContract()
    spec = contract.get_service_spec()
    assert isinstance(spec, ServiceSpec)
    assert spec.id == "coherence.inventory"
    assert len(spec.capabilities) > 0
    # Inventory has the most dependencies
    assert len(spec.dependencies) >= 3


def test_inventory_contract_health_check():
    contract = InventoryServiceContract()
    result = contract.health_check()
    assert isinstance(result, dict)


# -- Federation --

def test_federation_contract_spec():
    contract = FederationServiceContract()
    spec = contract.get_service_spec()
    assert isinstance(spec, ServiceSpec)
    assert spec.id == "coherence.federation"
    assert len(spec.capabilities) > 0


def test_federation_contract_health_check():
    contract = FederationServiceContract()
    result = contract.health_check()
    assert isinstance(result, dict)
