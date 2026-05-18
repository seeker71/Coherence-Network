"""Numeric schema sentinels for the coherence-substrate vocabulary."""
from __future__ import annotations

from app.services.substrate.category import BDomain, RBasic


def test_domain_numbers_follow_intentional_bands():
    """Domain blueprint instances carry a stable, documented banding."""
    assert {
        BDomain.CONCEPT: 1,
        BDomain.IDEA: 2,
        BDomain.SPEC: 3,
        BDomain.TASK: 4,
        BDomain.PRESENCE: 5,
        BDomain.MEMORY: 6,
        BDomain.LINEAGE: 7,
        BDomain.WITNESS: 8,
        BDomain.GRAMMAR: 9,
        BDomain.TRANSMISSION: 10,
        BDomain.RESOURCE: 11,
        BDomain.GUIDE: 12,
        BDomain.LANGUAGE_VIEW: 13,
        BDomain.KB_PAGE: 14,
        BDomain.SPECTRUM: 21,
        BDomain.HARMONIC: 22,
        BDomain.GEOMETRIC_FORM: 23,
        BDomain.POLARITY: 24,
        BDomain.TOPOLOGY: 25,
    } == {domain: int(domain) for domain in BDomain if domain is not BDomain.UNDEFINED}


def test_recipe_basic_numbers_keep_current_meaningful_bands():
    """Recipe verbs stay in their existing bands until a deliberate migration."""
    assert RBasic.REALIZE == 1
    assert RBasic.COMPOSE == 2
    assert RBasic.TRANSMIT == 3
    assert RBasic.TEND == 4
    assert RBasic.RESOLVE == 5
    assert RBasic.WITNESS == 6
    assert RBasic.ABSORB == 7
    assert RBasic.SCORE == 8
    assert RBasic.BLOCK == 9
    assert RBasic.CALL == 10
    assert RBasic.COND == 11
    assert RBasic.MATH == 12
    assert RBasic.COMPARE == 13
    assert RBasic.LOGIC == 14
    assert RBasic.CHOICE == 20
    assert RBasic.RESONANCE == 21
    assert RBasic.TRY == 30
