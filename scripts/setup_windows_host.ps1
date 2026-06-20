# Windows 11 host bootstrap for Coherence Network.
# Run from the repository root in Windows PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows_host.ps1

[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$ForceEnv
)

$ErrorActionPreference = "Stop"

function Add-UserPathEntry {
    param(
        [Parameter(Mandatory = $true)][string]$PathEntry,
        [switch]$Prepend
    )

    $resolved = [System.IO.Path]::GetFullPath($PathEntry)
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = @()
    if ($userPath) {
        $entries = $userPath -split ";" | Where-Object { $_ -ne "" }
    }

    $normalizedResolved = $resolved.TrimEnd("\")
    $entriesWithoutPath = @($entries | Where-Object { $_.TrimEnd("\") -ine $normalizedResolved })
    $newEntries = $entries
    if ($Prepend) {
        $newEntries = @($resolved) + $entriesWithoutPath
    } elseif ($entriesWithoutPath.Count -eq $entries.Count) {
        $newEntries = @($entries) + $resolved
    }

    $newPath = $newEntries -join ";"
    if ($newPath -ne $userPath) {
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "updated user PATH entry: $resolved"
    }

    $processEntries = @($env:Path -split ";" | Where-Object { $_ -ne "" })
    $processWithoutPath = @($processEntries | Where-Object { $_.TrimEnd("\") -ine $normalizedResolved })
    if ($Prepend) {
        $env:Path = (@($resolved) + $processWithoutPath) -join ";"
    } elseif ($processWithoutPath.Count -eq $processEntries.Count) {
        $env:Path = (@($processEntries) + $resolved) -join ";"
    }
}

function Require-Command {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Hint
    )

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "$Name is required. $Hint"
    }
    return $cmd.Source
}

function Install-WingetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($SkipInstall) {
        throw "$Name is missing and -SkipInstall was set."
    }

    Require-Command "winget" "Install App Installer from Microsoft Store or install $Name manually." | Out-Null
    Write-Host "installing $Name with winget..."
    winget install --exact --id $Id --accept-package-agreements --accept-source-agreements
}

if (-not (Test-Path ".git")) {
    throw "Run this script from the Coherence Network repository root."
}

$gitBash = Join-Path ${env:ProgramFiles} "Git\bin\bash.exe"
if (-not (Test-Path $gitBash)) {
    Install-WingetPackage -Id "Git.Git" -Name "Git for Windows"
}
if (-not (Test-Path $gitBash)) {
    throw "Git Bash was not found at $gitBash after installation."
}

$makeExe = "C:\Program Files (x86)\GnuWin32\bin\make.exe"
if (-not (Get-Command "make" -ErrorAction SilentlyContinue) -and -not (Test-Path $makeExe)) {
    Install-WingetPackage -Id "GnuWin32.Make" -Name "GNU Make"
}
if (Test-Path $makeExe) {
    Add-UserPathEntry (Split-Path $makeExe -Parent)
}

Require-Command "git" "Install Git for Windows." | Out-Null
Require-Command "py" "Install Python 3.12+ or enable the Python launcher." | Out-Null
Require-Command "node" "Install Node.js LTS/current for the web app." | Out-Null
Require-Command "npm.cmd" "Use npm.cmd from PowerShell because npm.ps1 may be blocked by execution policy." | Out-Null
Require-Command "rg" "Install ripgrep, for example: winget install BurntSushi.ripgrep.MSVC." | Out-Null
Require-Command "gh" "Install GitHub CLI, then run gh auth login." | Out-Null

$localBin = Join-Path $HOME ".local\bin"
New-Item -ItemType Directory -Force -Path $localBin | Out-Null
Add-UserPathEntry $localBin -Prepend

$pythonShim = Join-Path $localBin "python3"
$pythonShimCmd = Join-Path $localBin "python3.cmd"
[System.IO.File]::WriteAllText($pythonShim, "#!/usr/bin/env bash`nexec py -3 ""`$@""`n", [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText($pythonShimCmd, "@echo off`r`npy -3 %*`r`n", [System.Text.Encoding]::ASCII)
& $gitBash -lc "chmod +x ~/.local/bin/python3"

if ((-not (Test-Path "api\.env")) -or $ForceEnv) {
    Copy-Item "api\.env.example" "api\.env" -Force:$ForceEnv
    Write-Host "prepared api\.env"
}
if ((-not (Test-Path "web\.env.local")) -or $ForceEnv) {
    Copy-Item "web\.env.example" "web\.env.local" -Force:$ForceEnv
    Write-Host "prepared web\.env.local"
}

Write-Host ""
Write-Host "host checks:"
git --version
& py -3 --version
node --version
npm.cmd --version
rg --version | Select-Object -First 1
gh --version | Select-Object -First 1
if (Test-Path $makeExe) {
    & $makeExe --version | Select-Object -First 1
}

$ghAuthOutput = gh auth status -h github.com 2>&1
if ($LASTEXITCODE -eq 0) {
    $defaultGhConfigDir = Join-Path $env:APPDATA "GitHub CLI"
    $ghxProfileDir = Join-Path $HOME ".config\gh-seeker71"
    if (Test-Path (Join-Path $defaultGhConfigDir "hosts.yml")) {
        New-Item -ItemType Directory -Force -Path $ghxProfileDir | Out-Null
        Copy-Item (Join-Path $defaultGhConfigDir "hosts.yml") (Join-Path $ghxProfileDir "hosts.yml") -Force
        if (Test-Path (Join-Path $defaultGhConfigDir "config.yml")) {
            Copy-Item (Join-Path $defaultGhConfigDir "config.yml") (Join-Path $ghxProfileDir "config.yml") -Force
        }
        Write-Host "prepared ghx GitHub profile: $ghxProfileDir"
    }
} else {
    Write-Warning "GitHub CLI is installed but not authenticated. Run gh auth login before unbypassed make prompt-guide or PR checks."
}

Write-Host ""
Write-Host "Windows host bootstrap complete."
Write-Host "Open a new PowerShell window for the updated user PATH, or call make once with:"
Write-Host "  & '$makeExe' prompt-guide"
