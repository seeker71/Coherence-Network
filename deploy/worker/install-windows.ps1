# install-windows.ps1 — Register Coherence Network worker as a Windows Scheduled Task
# Runs the local_runner in loop mode, restarts on failure, survives reboots.
#
# Usage (run as Administrator):
#   powershell -ExecutionPolicy Bypass -File deploy\worker\install-windows.ps1
#
# To uninstall:
#   schtasks /Delete /TN "CoherenceNetworkWorker" /F

param(
    [string]$RepoDir = (Resolve-Path "$PSScriptRoot\..\..\").Path,
    [int]$Interval = 15,
    [int]$Timeout = 300,
    [string]$TaskName = "CoherenceNetworkWorker",
    [string]$PythonPath = "python"
)

$RunnerScript = Join-Path $RepoDir "api\scripts\local_runner.py"
$LogDir = Join-Path $RepoDir "api\logs"
$LogFile = Join-Path $LogDir "worker_service.log"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

# Build the command
$Arguments = "-u `"$RunnerScript`" --loop --interval $Interval --timeout $Timeout --no-self-update"

Write-Host "Coherence Network Worker — Windows Service Installer"
Write-Host "======================================================"
Write-Host "Repo:     $RepoDir"
Write-Host "Runner:   $RunnerScript"
Write-Host "Interval: ${Interval}s"
Write-Host "Timeout:  ${Timeout}s"
Write-Host "Log:      $LogFile"
Write-Host ""

# Check if task already exists
$existing = schtasks /Query /TN $TaskName 2>$null
if ($existing) {
    Write-Host "Task '$TaskName' already exists. Removing..."
    schtasks /Delete /TN $TaskName /F
}

# Create a wrapper batch script that the task scheduler runs
$WrapperScript = Join-Path $LogDir "run_worker.bat"
@"
@echo off
cd /d "$RepoDir"
set PYTHONUTF8=1
$PythonPath -u "$RunnerScript" --loop --interval $Interval --timeout $Timeout --no-self-update >> "$LogFile" 2>&1
"@ | Out-File -FilePath $WrapperScript -Encoding ASCII

# Register as a scheduled task that:
# - Runs at system startup
# - Restarts on failure (every 5 minutes, up to 3 times)
# - Runs whether user is logged on or not
$Action = New-ScheduledTaskAction -Execute $WrapperScript -WorkingDirectory $RepoDir
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -MultipleInstances IgnoreNew

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest -LogonType S4U

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Coherence Network federation worker — picks up tasks, executes via AI providers, pushes measurements"

Write-Host ""
Write-Host "Installed! Task: $TaskName"
Write-Host ""
Write-Host "Commands:"
Write-Host "  Start now:    schtasks /Run /TN `"$TaskName`""
Write-Host "  Check status: schtasks /Query /TN `"$TaskName`" /V"
Write-Host "  View log:     Get-Content -Tail 50 `"$LogFile`""
Write-Host "  Stop:         schtasks /End /TN `"$TaskName`""
Write-Host "  Uninstall:    schtasks /Delete /TN `"$TaskName`" /F"

# Start it now
Write-Host ""
Write-Host "Starting worker..."
schtasks /Run /TN $TaskName
Write-Host "Done. Worker is running."
