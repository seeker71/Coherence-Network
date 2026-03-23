' start-worker.vbs — Start Coherence Network worker silently in background
' Place a shortcut to this file in shell:startup to auto-start on login
'
' To install:
'   1. Right-click this file -> Create Shortcut
'   2. Press Win+R, type: shell:startup
'   3. Move the shortcut to the Startup folder
'
' To stop: taskkill /F /FI "WINDOWTITLE eq CoherenceWorker"

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\source\Coherence-Network\.claude\worktrees\infallible-goodall"
WshShell.Run "cmd /c ""set PYTHONUTF8=1&& python -u api\scripts\local_runner.py --loop --interval 15 --timeout 300 --no-self-update >> api\logs\worker_service.log 2>&1""", 0, False
