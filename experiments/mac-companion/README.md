# Sema Companion (macOS native)

The native macOS window into US — the local, present dashboard Urs asked for (native, not
the web observatory; the web/API may run underneath as a data source). A sibling in spirit
to the Android `sema-companion`, but a real AppKit/SwiftUI window on this Mac.

## Build & run

```sh
./build-app.sh
open build/SemaCompanion.app
```

No Xcode needed — SwiftPM + a hand-written `.app` bundle.

## Rooms

- **Presence** (live) — every mesh organ from `api.coherencycoin.com/api/hati/mesh/organs`,
  polled every 3s: heartbeat dot (listening + heard within 5 min), kind, discovery state,
  last-seen. This is "see the heartbeat of each available organ".
- **Resources** (live) — this Mac's own body read **natively** from Darwin (no shell, no
  web): CPU (`host_statistics` HOST_CPU_LOAD_INFO), memory (`host_statistics64` HOST_VM_INFO64
  + physical RAM), disk (volume capacity), network (`getifaddrs` byte deltas on en*/pdp_ip).
  GPU is honestly marked pending (needs IOKit).
- **Transcripts / Learning / Recognition** (framed, pending) — named rooms with their data
  lane named, not yet fed. The honest floor, shown in-app. Next lanes:
  - Transcripts ← `satsang-mesh-sync` outputs + live room capture
  - Learning ← `/api/models/learning-dashboard`
  - Recognition ← resemblyzer speaker enrollment + object recognition

## Direction

Grow the pending rooms; add per-organ resource detail (each organ streams its own
cpu/gpu/ram/disk/net); optionally a menu-bar presence so the mesh's pulse is always in view.
