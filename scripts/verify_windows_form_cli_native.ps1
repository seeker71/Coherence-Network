<#
Verify the standalone Windows form-cli native runtime floor.

The build step still uses the current bootstrap carrier plus clang as a local
oracle. The acceptance step strips runtime PATH before running the resulting
binary, proving the CLI surface does not call Go, clang, LLVM, or a table file
at runtime.
#>
[CmdletBinding()]
param(
    [string]$Bash = "",
    [string]$Go = "go",
    [string]$Clang = "",
    [switch]$KeepBinary
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Resolve-Tool {
    param(
        [string]$Requested,
        [string[]]$Names,
        [string[]]$Fallbacks
    )

    if ($Requested) {
        if (Test-Path -LiteralPath $Requested) {
            return (Resolve-Path -LiteralPath $Requested).Path
        }
        $cmd = Get-Command $Requested -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
        throw "Unable to find requested tool: $Requested"
    }

    foreach ($fallback in $Fallbacks) {
        if (Test-Path -LiteralPath $fallback) {
            return (Resolve-Path -LiteralPath $fallback).Path
        }
    }

    foreach ($name in $Names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Source
        }
    }

    throw "Unable to find required tool. Tried: $($Names -join ', ')"
}

function ConvertTo-GitBashPath {
    param([string]$Path)

    $full = (Resolve-Path -LiteralPath $Path).Path
    $drive = $full.Substring(0, 1).ToLowerInvariant()
    $rest = $full.Substring(2).Replace("\", "/")
    return "/$drive$rest"
}

function Invoke-FormCli {
    param(
        [string]$Exe,
        [string]$InputText,
        [string]$RuntimePath
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $Exe
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Environment["PATH"] = $RuntimePath

    $process = [System.Diagnostics.Process]::Start($psi)
    $process.StandardInput.Write($InputText)
    $process.StandardInput.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    if ($process.ExitCode -ne 0) {
        throw "form-cli exited with $($process.ExitCode)`nstdout:`n$stdout`nstderr:`n$stderr"
    }

    return $stdout
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$formDir = Join-Path $repoRoot "form"
$bashPath = Resolve-Tool -Requested $Bash -Names @("bash.exe", "bash") -Fallbacks @("C:\Program Files\Git\bin\bash.exe")
$goPath = Resolve-Tool -Requested $Go -Names @("go.exe", "go") -Fallbacks @("C:\Program Files\Go\bin\go.exe")
$clangPath = Resolve-Tool -Requested $Clang -Names @("clang.exe", "clang") -Fallbacks @("C:\Program Files\LLVM\bin\clang.exe")
$exe = Join-Path $formDir ".cache\form-cli-win.exe"

$oldPath = $env:PATH
try {
    $env:PATH = "$(Split-Path -Parent $goPath);$(Split-Path -Parent $clangPath);$oldPath"
    $formBashPath = ConvertTo-GitBashPath -Path $formDir
    & $bashPath -lc "cd '$formBashPath' && ./build-form-cli.sh .cache/form-cli-win.exe"
    if ($LASTEXITCODE -ne 0) {
        throw "build-form-cli.sh failed with exit code $LASTEXITCODE"
    }
} finally {
    $env:PATH = $oldPath
}

if (-not (Test-Path -LiteralPath $exe)) {
    throw "Expected native form-cli executable missing: $exe"
}

$runtimePath = "$env:SystemRoot\System32;$env:SystemRoot"
$oldPath = $env:PATH
try {
    $env:PATH = $runtimePath
    $runtimeGo = Get-Command go -ErrorAction SilentlyContinue
    $runtimeClang = Get-Command clang -ErrorAction SilentlyContinue
    $runtimeLlvm = Get-Command llvm-objdump -ErrorAction SilentlyContinue
    if ($runtimeGo -or $runtimeClang -or $runtimeLlvm) {
        throw "Sanitized runtime PATH still resolves a build/oracle tool"
    }
} finally {
    $env:PATH = $oldPath
}

$ping = Invoke-FormCli -Exe $exe -InputText "ping`n" -RuntimePath $runtimePath
if ($ping.Trim() -ne "pong") {
    throw "Unexpected ping response: $ping"
}

$verify = Invoke-FormCli -Exe $exe -InputText "verify`n" -RuntimePath $runtimePath
if ($verify -notmatch "coherent: this binary carries" -or $verify -notmatch "program running native on fkwu") {
    throw "Unexpected verify response: $verify"
}

$source = Invoke-FormCli -Exe $exe -InputText "source`n" -RuntimePath $runtimePath
if ($source -notmatch ";;;; ==== FILE: form-stdlib/minimal-surface.fk ====" -or $source -notmatch ";;;; ==== FILE: build-form-cli.sh ====") {
    throw "Embedded source proof missing expected genesis markers"
}

$size = (Get-Item -LiteralPath $exe).Length
Write-Host "PASS windows-form-cli-native exe=$exe bytes=$size"
Write-Host "PASS windows-form-cli-ping output=pong"
Write-Host "PASS windows-form-cli-verify native=fkwu embedded_source=true"
Write-Host "PASS runtime-toolchain-free path=$runtimePath go=absent clang=absent llvm_objdump=absent"
Write-Host "BUILD_CARRIER go=$goPath"
Write-Host "BUILD_ORACLE clang=$clangPath"

if (-not $KeepBinary) {
    Remove-Item -LiteralPath $exe -Force
}
