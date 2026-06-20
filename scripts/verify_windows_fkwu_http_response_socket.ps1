<#
Verify Windows fkwu HTTP response recipes over the socket host-call floor.

The build step uses Go and clang as local carriers/oracles to emit and compile
the Form-authored fkwu walker. The acceptance step strips runtime PATH before
executing the cached fkwu binary against the HTTP response loopback table,
proving request and response bytes use BML HTTP recipes over socket_listen/
port/connect/accept/send/recv/close without Go, clang, LLVM, http_get, or
sock_request at runtime.
#>
[CmdletBinding()]
param(
    [string]$Bash = "",
    [string]$Go = "go",
    [string]$Clang = "",
    [switch]$KeepCache
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

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$formDir = Join-Path $repoRoot "form"
$cacheDir = Join-Path $formDir "form-stdlib\.cache\fourth"
$bashPath = Resolve-Tool -Requested $Bash -Names @("bash.exe", "bash") -Fallbacks @("C:\Program Files\Git\bin\bash.exe")
$goPath = Resolve-Tool -Requested $Go -Names @("go.exe", "go") -Fallbacks @("C:\Program Files\Go\bin\go.exe")
$clangPath = Resolve-Tool -Requested $Clang -Names @("clang.exe", "clang") -Fallbacks @("C:\Program Files\LLVM\bin\clang.exe")

New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
Remove-Item -LiteralPath (Join-Path $cacheDir "fkwu-*") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $cacheDir "t-http-client-socket-response-*.txt") -Force -ErrorAction SilentlyContinue

$formBashPath = ConvertTo-GitBashPath -Path $formDir
$oldPath = $env:PATH
try {
    $env:PATH = "$(Split-Path -Parent $goPath);$(Split-Path -Parent $clangPath);$oldPath"
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $validateOut = & $bashPath -lc "cd '$formBashPath' && ./validate.sh form-stdlib/core.fk form-stdlib/http-client.fk form-stdlib/tests/http-client-socket-response-band.fk" 2>&1
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($LASTEXITCODE -ne 0) {
        throw "http-client-socket-response validate failed with exit code $LASTEXITCODE`n$($validateOut -join "`n")"
    }
} finally {
    $env:PATH = $oldPath
}

$validateText = $validateOut -join "`n"
if ($validateText -notmatch "0 divergent") {
    throw "http-client-socket-response validate did not report zero divergence`n$validateText"
}
if ($validateText -notmatch "fourth arm: 1 band\(s\) four-way") {
    throw "http-client-socket-response did not run as a fkwu fourth-arm band`n$validateText"
}

$fkwu = Get-ChildItem -LiteralPath $cacheDir -Filter "fkwu-*" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
$table = Get-ChildItem -LiteralPath $cacheDir -Filter "t-http-client-socket-response-*.txt" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $fkwu) {
    throw "Missing cached fkwu binary under $cacheDir"
}
if (-not $table) {
    throw "Missing cached http-client-socket-response fkwu table under $cacheDir"
}

$runtimeExe = Join-Path ([System.IO.Path]::GetTempPath()) ("fkwu-http-client-socket-response-" + [guid]::NewGuid().ToString("N") + ".exe")
Copy-Item -LiteralPath $fkwu.FullName -Destination $runtimeExe -Force

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

    $run = @(& $runtimeExe $table.FullName 0)
    if ($LASTEXITCODE -ne 0) {
        throw "fkwu http-client-socket-response table failed with exit code $LASTEXITCODE"
    }
} finally {
    $env:PATH = $oldPath
    Remove-Item -LiteralPath $runtimeExe -Force -ErrorAction SilentlyContinue
}

if ($run.Count -lt 128) {
    throw "Expected result plus 127 fkwu arm counters, got $($run.Count) line(s)"
}
if ([string]$run[0] -ne "8191") {
    throw "Unexpected http-client-socket-response verdict from fkwu: $($run[0])"
}

$requiredTags = @(120, 121, 122, 123, 124, 125, 126)
foreach ($tag in $requiredTags) {
    $hits = [int64]$run[$tag]
    if ($hits -le 0) {
        throw "Expected fkwu socket tag $tag to be exercised, got hit count $hits"
    }
}

Write-Host "PASS windows-fkwu-http-client-socket-response verdict=8191"
Write-Host "PASS fkwu-socket-tags tags=$($requiredTags -join ',')"
Write-Host "PASS runtime-toolchain-free path=$runtimePath go=absent clang=absent llvm_objdump=absent"
Write-Host "PASS no-http-get-no-sock-request runtime proof=socket-tags"
Write-Host "BUILD_CARRIER go=$goPath"
Write-Host "BUILD_ORACLE clang=$clangPath"
Write-Host "FKWU $($fkwu.FullName)"
Write-Host "TABLE $($table.FullName)"

if (-not $KeepCache) {
    Remove-Item -LiteralPath $table.FullName -Force -ErrorAction SilentlyContinue
}
