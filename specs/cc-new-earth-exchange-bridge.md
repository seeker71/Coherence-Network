---
idea_id: coherence-credit
status: done
source:
  - file: api/app/services/cc_exchange_adapter.py
    symbols: [ExchangeAdapter, NewEarthAdapter, CESAdapter, initiate_swap, confirm_swap]
  - file: api/app/models/cc_exchange.py
    symbols: [ExchangeQuote, SwapRequest, SwapResult, SwapConfirmation, AdapterInfo]
  - file: api/app/routers/cc_exchange.py
    symbols: [list_adapters, get_quote, initiate_swap, get_swap, confirm_swap, get_history]
  - file: api/app/services/cc_treasury_service.py
    symbols: [record_swap_out, record_swap_in]
requirements:
  - Pluggable adapter interface for external exchanges
  - New Earth Exchange adapter (manual settlement, upgradeable to API)
  - Community Exchange System adapter (mutual credit interop)
  - Quote endpoint with 15-minute validity
  - Swap initiation with treasury ledger recording
  - Manual confirmation flow for settlement
  - Swap history per user
  - Treasury coherence invariant maintained through swaps
done_when:
  - GET /api/cc/exchange/adapters returns new_earth and ces
  - POST /api/cc/exchange/quote returns valid quote with rate
  - POST /api/cc/exchange/swap creates pending swap
  - POST /api/cc/exchange/swap/{id}/confirm settles the swap
  - Treasury coherence score remains >= 1.0 after swaps
  - All existing CC tests continue passing
  - 'file_exists("api/app/services/cc_exchange_adapter.py")'
  - 'symbol_in_file("api/app/services/cc_exchange_adapter.py", "ExchangeAdapter")'
  - 'symbol_in_file("api/app/services/cc_exchange_adapter.py", "NewEarthAdapter")'
  - 'symbol_in_file("api/app/services/cc_exchange_adapter.py", "CESAdapter")'
  - 'symbol_in_file("api/app/services/cc_exchange_adapter.py", "initiate_swap")'
  - 'symbol_in_file("api/app/services/cc_exchange_adapter.py", "confirm_swap")'
  - 'file_exists("api/app/models/cc_exchange.py")'
  - 'symbol_in_file("api/app/models/cc_exchange.py", "ExchangeQuote")'
  - 'symbol_in_file("api/app/models/cc_exchange.py", "SwapRequest")'
  - 'symbol_in_file("api/app/models/cc_exchange.py", "SwapResult")'
  - 'symbol_in_file("api/app/models/cc_exchange.py", "SwapConfirmation")'
  - 'symbol_in_file("api/app/models/cc_exchange.py", "AdapterInfo")'
  - 'file_exists("api/app/routers/cc_exchange.py")'
  - 'symbol_in_file("api/app/routers/cc_exchange.py", "list_adapters")'
  - 'symbol_in_file("api/app/routers/cc_exchange.py", "get_quote")'
  - 'symbol_in_file("api/app/routers/cc_exchange.py", "initiate_swap")'
  - 'symbol_in_file("api/app/routers/cc_exchange.py", "get_swap")'
  - 'symbol_in_file("api/app/routers/cc_exchange.py", "confirm_swap")'
  - 'symbol_in_file("api/app/routers/cc_exchange.py", "get_history")'
  - 'file_exists("api/app/services/cc_treasury_service.py")'
  - 'symbol_in_file("api/app/services/cc_treasury_service.py", "record_swap_out")'
  - 'symbol_in_file("api/app/services/cc_treasury_service.py", "record_swap_in")'
  - 'pytest_passes("api/tests/test_cc_exchange.py")'
test: python -m pytest api/tests/test_cc_exchange.py -v
constraints:
  - No unbacked CC may be created through swaps
  - Manual settlement is the default until external APIs are available
  - Swap-out burns CC immediately; swap-in mints only on confirmation
---

# CC ↔ New Earth Exchange Bridge

## Overview

Bridge between Coherence Credits and external exchange systems, starting with
Sacha Stone's New Earth Exchange and the Community Exchange System (CES).

## Architecture

The adapter pattern allows pluggable exchange connections. Each adapter
implements: `get_rate`, `health_check`, with the service providing
`get_quote`, `initiate_swap`, `confirm_swap`.

Settlement starts manual (human confirms both sides) and upgrades to
API-based when external systems publish protocols. The adapter interface
is the same either way.

## Swap Flow

1. User requests a quote (`POST /exchange/quote`)
2. User initiates swap (`POST /exchange/swap`)
   - CC-out: CC burned immediately from user balance
   - CC-in: CC held until confirmation
3. External settlement happens (manual or API)
4. User/system confirms (`POST /exchange/swap/{id}/confirm`)
   - CC-in: CC minted to user on confirmation

## Security

- Treasury coherence invariant holds: no unbacked CC
- Swap-out burns before external settlement (CC side is risk-free)
- Swap-in mints only after confirmation (no free CC)
- All swaps recorded in append-only treasury ledger

## Out of Scope

- None.

## Known Gaps

- None.

## Risks and Assumptions

- None.

## Files

- `api/app/services/cc_exchange_adapter.py`
- `api/app/models/cc_exchange.py`
- `api/app/routers/cc_exchange.py`
- `api/app/services/cc_treasury_service.py`

## Verification

```bash
python -m pytest api/tests/test_cc_exchange.py -v
```

## Acceptance Tests

- `api/tests/test_cc_exchange.py`

## Requirements

- [ ] GET /api/cc/exchange/adapters returns new_earth and ces
- [ ] POST /api/cc/exchange/quote returns valid quote with rate
- [ ] POST /api/cc/exchange/swap creates pending swap
- [ ] POST /api/cc/exchange/swap/{id}/confirm settles the swap
- [ ] Treasury coherence score remains >= 1.0 after swaps

