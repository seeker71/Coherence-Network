---
category: financial
purpose: bank accounts, fiat reserves, crypto, investments, lines of credit
privacy: category-level entries public · specifics in encrypted treasury
---

# Financial holdings

What can enter under this category:

- **Bank accounts** — checking, savings, money market, business
  operating, foreign-currency
- **Fiat reserves** — physical cash holdings, foreign-currency cash
- **Cryptocurrency** — BTC, ETH, USDC, USDT, ATOM, SOL, custom-token
  positions, hardware-wallet holdings, exchange balances
- **Investments** — brokerage accounts, retirement accounts (401k,
  IRA, Roth), index funds, individual equities, bonds, ETFs
- **Lines of credit** — personal credit lines, business LOCs, HELOCs
- **Receivables** — outstanding invoices, loan-receivable positions,
  contractual future income
- **Other instruments** — life insurance cash value, annuities,
  pension claims, equity in private companies, partnership interests

## How financial holdings enter the body

Most financial assets do **not** transfer title to the wrapper the
way a vehicle or property does. Instead, the cell maintains legal
custody and grants the wrapper either:

- **Visibility**: the wrapper can see balances and movements for
  proprioception purposes (the substrate's coherent picture of the
  body's resources)
- **Operating authority**: the wrapper can execute transactions on
  the cell's behalf, under explicit signed terms (e.g., a small
  monthly contribution to network operations, a treasury-pool
  participation)
- **Custody transfer**: in specific cases (e.g., crypto held at a
  multi-sig wallet the wrapper co-controls), legal custody actually
  moves

The default is visibility-without-custody. The cell remains the
legal account holder; the wrapper has the read-permission and any
specific operating authority the cell signs.

## Privacy

Public-level entries in this file: account *kind*, custodian *type*,
denomination *currency*, and a high-level magnitude bucket (e.g.,
*minor*, *moderate*, *significant*) — not exact balances, not
account numbers, not access credentials.

Specifics live in the wrapper's encrypted treasury record. That
record is readable by the cell, by the wrapper's operating quorum
under the signed terms, and not by anyone else without the cell's
explicit per-event consent.

## Inventory template

When ready to record an entry, copy this block and fill in:

```yaml
- kind: bank-account | crypto | investment | line-of-credit | other
  custodian_type: "what kind of institution holds it (bank name not required)"
  denomination: "USD | EUR | BTC | ETH | etc."
  magnitude: minor | moderate | significant     # category-level only
  relationship: held | access-granted | proposed
  primary_shepherd: cell_id_or_name
  wrapper_relationship: visibility-only | operating-authority | custody-transferred
  ceremony_date: YYYY-MM-DD
  notes: "anything the registry should know without revealing specifics"
```

## Currently held (this cell's inventory)

```yaml
# Awaiting inventory.
# When you're ready, fill in entries below and remove this comment.
```

## Awaiting inventory — slots

The body is patient. The cell is invited to populate when ready,
asset by asset, as discernment clarifies what should be held visibly,
what should retain custody, and what is appropriate to bring under
operating authority.
