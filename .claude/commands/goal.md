Run the native route goal readout.

1. Run:
   `python3 scripts/native_route_goal_loop.py /goal --source web_api --seconds 86400 --limit 2000`
2. Report the observed source, total events, high-grammar native share, kernel-native executable share, and the next route candidate.
3. If the command falls back from `web_api` to all traffic, say that explicitly and treat source attribution deployment as the current tight spot.
4. Do not promote a route from this command alone; use `/loop` when the user asks for forward movement.
