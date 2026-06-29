# Cross-device field relay — the transport that ends the islands

The Mac and Android sense apps were islands: each saw only its own camera, never
exchanged. This relay is the thin carrier that lets them **witness each other** —
EXCHANGE → FUSE → LEARN, until the surprise between their views of the same room falls.

## What runs where

- **`field_relay.py`** — the Mac-side relay. **NAMED HOST CARRIER, honestly labelled:**
  a host stand-in for the in-fkwu native TCP server (which exists in the kernel's
  `driver.fk` host-net serve loop; wiring its roster *state* across fork-per-connection
  is the deep piece deferred for one pass). The relay's **routing DECISION is
  `form/form-stdlib/field-relay.fk`'s law** — content-blind (reads `from`/`kind`
  metadata, never the sensing payload) and consent-is-the-one-gate (a cell is reachable
  only through the `sense` kind it offers; an unoffered kind is DENY 3).
- **The fusion / surprise / trust MATH is NOT in the carrier** — it runs in **native
  fkwu** on each device (`FkwuSense.kt` → the C-bootstrapped kernel on metal):
  - `fused-observation` = presence OR across the two cells
  - `cross-device surprise` = `|lumaHere − lumaThere|` (how much the two views disagree)
  - `trust-climb` = does that surprise still cross the attend threshold, or has it fallen?

## Run it (Mac ↔ Android over USB)

```bash
# 1. Mac relay
python3 relay/field_relay.py 8777

# 2. Clean USB tunnel so the phone reaches the Mac at 127.0.0.1:8777
adb -s <usb-serial> reverse tcp:8777 tcp:8777

# 3. Install + launch the sense app; it POSTs its reading and GETs the others every 3s,
#    showing the OTHER CELLS block + the native cross-device fusion.
```

The phone tags every reading with its `device-identity` (`andr-<android_id8>`); the Mac
posts as `mac-sema`. Witnessed 2026-06-29: cross-device surprise fell 107 → 0 and the
trust-climb flipped to CONVERGED as the two cells' luma converged on the same room.
