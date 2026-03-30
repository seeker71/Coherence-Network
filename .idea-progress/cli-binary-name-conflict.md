# Idea Progress — cli-binary-name-conflict

## Current task
- Phase: impl (task_883b0be9d0ed319c)
- Status: COMPLETE
- Commit: 41c54b26

## Completed phases
- **impl**: Renamed CLI binary references from cc to coh across cc.mjs, README.md, and CLAUDE.md. package.json already had coh and coherence entries. Deprecation warning for cc invocation was already in place.

## Key decisions
- coh is the primary binary name; cc remains as deprecated alias
- coherence also registered as a bin entry for discoverability
- Deprecation warning prints to stderr when invoked as cc

## Blockers
- None
