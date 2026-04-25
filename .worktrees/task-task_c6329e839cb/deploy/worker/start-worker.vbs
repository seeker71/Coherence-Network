' start-worker.vbs — Start Coherence Network worker from origin/main
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\source\Coherence-Network"
WshShell.Run "cmd /c ""cd /d C:\source\Coherence-Network && git checkout main && git pull origin main && set PYTHONUTF8=1&& python -u api\scripts\local_runner.py --loop --interval 15 --timeout 300 --no-self-update >> api\logs\worker_service.log 2>&1""", 0, False
