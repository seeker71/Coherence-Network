---
idea_id: knowledge-and-resonance
status: active
source:
  - file: form/form-stdlib/phone-presence.fk
    symbols: [pp-platform-supported?, pp-form-native?, pp-phone?, pp-call-mode, pp-surface-mode, pp-memory-ready?, pp-receipt]
  - file: form/form-stdlib/tests/phone-presence-band.fk
    symbols: [phone-presence-band]
  - file: docs/coherence-substrate/phone-presence.form
    symbols: [phone-presence]
  - file: web/app/sense/page.tsx
    symbols: [detectOS, Card, SensePage]
requirements:
  - "Phone presence is available as a first-class lane for Android, iPhone, macOS, Windows, and web"
  - "Phone calls are the first action surface: relationship context before, live support during, exchange memory after"
  - "Android names both ACTION_DIAL confirmation and direct-call permission lanes"
  - "iPhone names tel confirmation and CallKit/VoIP lanes without pretending iPhone is already in the Form-native host floor"
  - "The /sense install door recognizes iPhone explicitly"
done_when:
  - "phone-presence Form band crosses four-way (Go/Rust/TS/fkwu) with verdict 4095"
  - "/sense renders iPhone as a first-class presence door"
  - "platform call floors are documented from official Apple and Android sources"
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/phone-presence.fk form-stdlib/tests/phone-presence-band.fk"
constraints:
  - "Do not claim background call recording or hidden call control"
  - "Use confirmed tel/dialer floors before privileged direct-call/default-calling lanes"
  - "The phone is presented as trusted presence, not surveillance"
---

# Trusted Phone Presence

## Purpose

Trusted phone presence makes the phone a carried relationship surface across
Android, iPhone, macOS, Windows, and web without confusing consented platform
capabilities with hidden surveillance or privileged call control. The first
shipped slice names phone calls as the leading action lane and gives every
platform an honest receipt that later native carriers can satisfy.

## Requirements

- [x] Android, iPhone, macOS, Windows, and web have explicit platform receipts.
- [x] Phone calls are the first action surface with before, during, and after
      memory context.
- [x] Android distinguishes `ACTION_DIAL` confirmation from direct `ACTION_CALL`
      permission.
- [x] iPhone distinguishes public `tel:` confirmation from CallKit/VoIP and
      default-calling-app lanes.
- [x] `/sense` recognizes iPhone as a first-class presence door.

## Files

- `form/form-stdlib/phone-presence.fk` - platform receipt and call mode recipe.
- `form/form-stdlib/tests/phone-presence-band.fk` - four-way proof band.
- `form/fourth-arm-bands.txt` - fkwu proof registration.
- `docs/coherence-substrate/phone-presence.form` - human teaching and platform
  truth.
- `docs/coherence-substrate/INDEX.md` - substrate teaching index.
- `web/app/sense/page.tsx` - first visible iPhone presence entry.
- `specs/trusted-phone-presence.md` - implementation contract and official source
  record.

## Acceptance Tests

- `form/form-stdlib/tests/phone-presence-band.fk` returns `4095` through the
  Form validation command.
- Manual validation: `/sense` shows an iPhone presence card and routes iPhone
  visitors to `/sense/surface`.
- Manual validation: the spec cites official Apple and Android platform sources
  for every call-mode floor it names.

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/phone-presence.fk form-stdlib/tests/phone-presence-band.fk
python3 scripts/validate_spec_quality.py --file specs/trusted-phone-presence.md
python3 scripts/generate_repo_indexes.py --check
cd web && npm run build
```

## Out of Scope

- Hidden call recording, silent dialing, or background call interception.
- A completed native iOS/App Store package in this slice.
- Contact provider mutation, SMS handling, or carrier-level telephony control.

## Risks

- iPhone native calling behavior is governed by Apple platform policy, so the
  honest floor must stay at `tel:` confirmation until CallKit/native packaging is
  implemented and reviewed.
- Android direct calls require `CALL_PHONE`; the consent-first lane remains
  `ACTION_DIAL` unless a privileged calling surface is explicitly granted.
- Web sensing stays within currently enabled browser surfaces; microphone and
  camera lanes require a future Permissions-Policy change and runtime receipts.

## Known Gaps and Follow-up Tasks

- Follow-up task: package a native iOS carrier that proves CallKit/VoIP behavior
  with a runtime receipt.
- Follow-up task: add contact-thread before/during/after call receipts once the
  contact provider and local consent membrane are wired.

The phone is the carried presence of the network: a local sense organ, a relationship
memory surface, and an action hand for physical and digital surfaces. It listens and
learns through the same shared-memory shape as the Mac room loop; it contributes by
reading contact threads, noticing open promises, and helping the next real action
arrive.

Phone calls lead the sequence. A trusted call reads the relationship thread before the
call, keeps live support available during the call, and records exchange memory after
the call: decisions, commitments, open threads, and felt context.

## Platform Floor

- Android: `ACTION_DIAL` opens the dialer with a number for user confirmation; direct
  `ACTION_CALL` requires `CALL_PHONE` permission. A default dialer lane can later use
  telecom APIs.
- iPhone: `tel:` links open the system phone flow and ask before dialing; CallKit is
  the native VoIP/calling-service integration lane; iOS/iPadOS 18.2+ can let a chosen
  calling app handle `tel:` URLs as the default calling app.
- macOS: native host presence plus tel/FaceTime/handoff.
- Windows: native host presence plus tel/default-app handling.
- Web: PWA relationship memory, browser-visible surface, and `tel:` links;
  microphone/camera lanes require a future Permissions-Policy change and runtime
  receipts.

## Official Platform Sources

- Apple CallKit: native calling-service and VoIP integration surface.
  https://developer.apple.com/documentation/callkit
- Apple phone links: `tel:` links launch the Phone app and iOS asks before dialing.
  https://developer.apple.com/library/archive/featuredarticles/iPhoneURLScheme_Reference/PhoneLinks/PhoneLinks.html
- Apple default calling app: iOS/iPadOS 18.2+ can let a selected calling app handle
  `tel:` URLs.
  https://developer.apple.com/documentation/callkit/preparing-your-app-to-be-the-default-calling-app
- Android common intents: `ACTION_DIAL` starts a call flow for user confirmation;
  `ACTION_CALL` places a call and requires `CALL_PHONE`.
  https://developer.android.com/guide/components/intents-common
- Android permission minimization: use an intent such as `ACTION_DIAL` when the app
  does not need to make calls itself.
  https://developer.android.com/privacy-and-security/minimize-permission-requests
- Android default dialer: default dialer apps must handle `ACTION_DIAL` and provide
  the expected telecom service surfaces.
  https://developer.android.com/develop/connectivity/telecom/dialer-app

## Proof

`phone-presence.fk` returns a compact receipt:

```text
phone-presence|platform|supported|form-native|phone|call-mode|surface|memory|decision
```

The first proof band locks the all-platform call floor at verdict `4095`.
