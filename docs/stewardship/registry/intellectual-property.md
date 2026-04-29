---
category: intellectual-property
purpose: patents, trademarks, copyrights, trade secrets, domain names, brand assets
privacy: category-level entries public · valuation and contract specifics in wrapper records
---

# Intellectual property

What can enter under this category:

- **Patents** — granted, pending, provisional
- **Trademarks** — registered, common-law, pending registration
- **Copyrights** — books, music, software, visual art, choreography,
  recorded teachings
- **Trade secrets** — proprietary processes, formulas, methodologies
  the cell holds and chooses to bring under collective stewardship
- **Domain names** — DNS holdings, web property
- **Brand assets** — logos, marks, names, identity systems
- **Open-source contributions** — author rights to projects already
  released under permissive licenses

## How IP enters the body

IP is unusually portable. Title can transfer to the wrapper without
the asset moving anywhere physically. Common patterns:

- **Title transfer**: the wrapper becomes the legal owner; the cell
  retains attribution and any agreed shepherd rights (e.g., approval
  over derivative works)
- **Exclusive license to wrapper**: the cell retains title; the
  wrapper holds the right to use, license further, and enforce
- **Non-exclusive license to wrapper**: the cell and wrapper both
  hold rights
- **Public dedication**: the cell donates the IP to the public
  domain via the wrapper's dedication ceremony

For cells whose IP is their living (writers, musicians, inventors),
the wrapper's job is often to handle licensing logistics so the cell
can focus on creative work — the wrapper receives royalties, pays the
cell their agreed share through the cooperative pool, and handles
enforcement against unauthorized use.

## Story Protocol integration

For digital IP especially, the network's existing
`story-protocol-integration` spec provides on-chain registration of
IP assets with content hashes, derivative tracking, and x402
micropayment settlement. IP entered here can be registered through
that pipeline so its provenance is walkable on-chain in addition to
in our graph.

## Privacy

Public-level: kind of IP, broad nature (a patent in *electromechanical
domain*, a copyrighted body of work in *contemplative practice
writings*), title status, wrapper relationship. **Not public**: full
text of unpublished works, exact financial terms of license deals,
trade-secret content itself.

## Inventory template

```yaml
- kind: patent | trademark | copyright | trade-secret | domain-name | brand-asset | other
  broad_description: "what kind of IP, in what domain"
  status: granted | pending | registered | unregistered | published | unpublished
  relationship: held | access-granted | proposed
  primary_shepherd: cell_id_or_name
  wrapper_relationship: title-transferred | exclusive-license | non-exclusive-license | story-protocol-registered | public-domain
  ceremony_date: YYYY-MM-DD
  notes: "anything the registry should know"
```

## Currently held (this cell's inventory)

```yaml
# Awaiting inventory.
# Any patents, copyrights, domain names, trademarks, or written/recorded
# bodies of work the cell wants to bring under collective stewardship.
```

## Awaiting inventory — slots

Likely candidates: domain names the cell holds, any
written/recorded/published bodies of work, any trademarks or
brand-marks, any patents (granted or pending), any open-source
projects the cell has authored.
