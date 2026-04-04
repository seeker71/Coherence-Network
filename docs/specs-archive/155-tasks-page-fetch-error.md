# Spec 155: Tasks page fetch error — client-side CORS fix

## Purpose

Fix the /tasks page (and all client-side pages) which showed "Error: TypeError: Failed to fetch" because browser-side API calls bypassed the Next.js proxy and hit CORS. The fix ensures `getApiBase()` returns an empty string in the browser so all client fetches route through the Next.js rewrite proxy.

## Requirements

- [x] `getApiBase()` returns `""` when running in the browser and pointing at a remote API
- [x] `getApiBase()` returns the full URL for server components (SSR)
- [x] Client-side pages make relative fetch calls (`/api/agent/tasks`) not absolute (`https://api.coherencycoin.com/api/agent/tasks`)
- [x] No CORS errors in browser DevTools on any client-side page
- [x] Tasks page loads with real task data (count > 0)

## Files to Create/Modify

- `web/lib/api.ts` — `getApiBase()` browser detection (modified)

## Out of Scope

- Tasks page UX redesign (separate spec)
- Server component CORS (not affected — SSR fetches don't use browser CORS)
- API-side CORS headers (the proxy eliminates the need)

## Acceptance Tests

- Existing tests pass: `python3 -m pytest api/tests/ -x --tb=short -q`
- Web build succeeds: `cd web && npx next build`

## Verification

```bash
# Verify API is healthy
curl -s https://api.coherencycoin.com/api/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])"
# Expected: ok

# Verify tasks endpoint returns data
curl -s https://api.coherencycoin.com/api/agent/tasks?limit=1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'total={d.get(\"total\",0)}')"
# Expected: total > 0

# Verify web page returns 200
curl -sI https://coherencycoin.com/tasks | head -1
# Expected: HTTP/2 200
```

- Manual: visit `https://coherencycoin.com/tasks` — page shows task list, no fetch errors
- Manual: open browser DevTools Network tab — requests go to `/api/agent/tasks` (relative path)
- Manual: visit `/contributions`, `/contributors`, `/assets`, `/friction` — all load data without CORS errors

## Risks and Assumptions

- Assumes Next.js rewrite `/api/:path*` → API base is configured in `next.config.ts` (confirmed)
- Proxy adds ~1ms latency per request (acceptable)
- `typeof window !== "undefined"` correctly detects browser context in Next.js

## Known Gaps and Follow-up Tasks

- Tasks page needs the same UX cleanup as other pages (stat cards, badges, formatted dates) — tracked as separate idea `ux-tasks-page-redesign`
- None: the CORS fix is complete and deployed
