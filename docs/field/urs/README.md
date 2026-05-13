# Coherence Field Listening Analysis

Local workspace for analyzing what entered Urs's field through Audible, YouTube, and YouTube Music.

## Current State
- Libation is installed at `/Applications/Libation.app`.
- Libation settings/database were initialized at `~/Library/Application Support/Libation`.
- Audible web login succeeded through Playwright on 2026-05-07.
- Authenticated Audible exports are under `/Users/ursmuff/CoherenceFieldAnalysis/input/audible/playwright/`:
  - `audible-listen-history.json` - visible web listen history.
  - `audible-purchase-history-2016-2026.json` - year-filtered purchases for the last ten years plus current year.
  - `audible-library.json` - current library holdings from all visible library pages.
- `trace/audible_history_spectrum.json` carries an effective Audible listening trace:
  - direct visible listen-history rows where Audible exposes them.
  - purchase-date approximation for purchased works that do not have a direct visible listen row.
  - duration-weighted monthly influence using Audible catalog runtime length, with event counts kept as secondary context.
- `trace/audible_duration_metadata.json` carries compact Audible catalog runtime metadata used by the duration-weighted trace.
- `trace/youtube_podcast_spectrum.json` carries the podcast-shaped YouTube influence wave. RSS-era subscriptions are not in the local source body yet, so this treats YouTube as the current podcast surface and marks estimated episode lengths when Takeout lacks duration.
- Local Google Takeout / YouTube history archives are named in `source-bodies/registry.json`; raw archives remain in `/Users/ursmuff/Downloads` while compact event traces circulate here.

## Field Story Structure

- `anchors/` holds hand-tended reference points that shape interpretation.
- `source-bodies/` names the raw archives, exports, browser traces, PDFs, and project bodies that remain in local custody while compact traces circulate through the repo.
- `input/` holds explicit seeds for the next ingest or encounter breath.
- `trace/` holds machine-readable indexes, hashes, and compact source evidence.
- `output/` holds human-readable stories and reports generated from the trace.
- `tools/` holds the small builders that digest source bodies into trace and output artifacts.

## Source Bodies

- `source-bodies/registry.json` is the custody map for local source-body groups, exact paths, glob patterns, ingestion policies, and publication boundaries.
- Bulky source bodies stay in `/Users/ursmuff/CoherenceFieldAnalysis` or `/Users/ursmuff/Downloads` unless a later breath promotes a specific shape into this repo.
- Builders read the registry and publish only compact counts, hashes, summaries, and evidence levels.

## Local Source Body Slots
- `/Users/ursmuff/CoherenceFieldAnalysis/input/audible/` receives Libation exports, preferably `libation-library.json` or `libation-library.csv`.
  - Playwright-authenticated Audible exports in `/Users/ursmuff/CoherenceFieldAnalysis/input/audible/playwright/` are loaded automatically.
- `/Users/ursmuff/CoherenceFieldAnalysis/input/youtube/` receives Google Takeout files:
  - `Takeout/YouTube and YouTube Music/history/watch-history.json`
  - or `watch-history.html`
  - optionally `My Activity/YouTube/MyActivity.json` or `.html` if Takeout's YouTube history is incomplete.
- `anchors/manual_reading_anchors.json` - manual seed anchors already provided by Urs.
- `/Users/ursmuff/CoherenceFieldAnalysis/input/browser/local_browser_events.jsonl` is generated from local Chrome/Chromium traces when service exports are not available.
- `input/encounter_next_breath.txt` is a repo-held seed for the next encounter pass, not a source-body registry.

## Export Commands
After Audible login + scan in Libation:

```bash
/Applications/Libation.app/Contents/MacOS/LibationCli scan
/Applications/Libation.app/Contents/MacOS/LibationCli export --path /Users/ursmuff/CoherenceFieldAnalysis/input/audible/libation-library.json --json
/Applications/Libation.app/Contents/MacOS/LibationCli export --path /Users/ursmuff/CoherenceFieldAnalysis/input/audible/libation-library.csv --csv
```

For YouTube / YouTube Music, use Google Takeout with `YouTube and YouTube Music` selected and History exported as JSON. The expected file is:

```text
Takeout/YouTube and YouTube Music/history/watch-history.json
```

## Run

```bash
python3 /Users/ursmuff/CoherenceFieldAnalysis/field_listening_analyzer.py \
  --root /Users/ursmuff/CoherenceFieldAnalysis
```

If Audible/Google account auth creates friction, collect local browser traces first:

```bash
python3 /Users/ursmuff/CoherenceFieldAnalysis/local_browser_history_collector.py
python3 /Users/ursmuff/CoherenceFieldAnalysis/field_listening_analyzer.py \
  --root /Users/ursmuff/CoherenceFieldAnalysis
```

Outputs:
- `output/normalized_events.jsonl`
- `output/frequency_summary.json`
- `output/field_report.md`
