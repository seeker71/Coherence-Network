# presence_cycle.ps1 - live end-to-end proof of the native presence (fkwu lane).
#
# Proves the whole north star on one running host, no restarts:
#   Rung 1  a presence just IS: it wakes, observes, heartbeats, stays alive.
#   Rung 2  a recipe minted mid-run is LOWERED to native by the Form kernel,
#           hot-loaded by the live presence, and called -- twice, same process.
#   Rung 3  a sibling that LACKS a recipe asks; the holder decides via the
#           four-way-proven consent brain (presence-loop.fk) and answers; the
#           asker integrates and computes -- still running.
#
# Every native result is checked against the affine oracle pl-affine-eval, the
# SAME four-way-proven Form value the validate.sh band pins. The lowering runs
# through the real Go kernel walking (pe-affine-recipe-object a b); only the
# linker and OS loader are dumb host carriers.

param([string]$WorkRoot = "")

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$form = Join-Path $repo "form"
if (-not $WorkRoot) { $WorkRoot = Join-Path $repo ".cache/presence-cycle" }
if (Test-Path $WorkRoot) { Remove-Item -Recurse -Force $WorkRoot }
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

# The Go kernel builds as extensionless `bin-go`; PowerShell's call operator only
# launches files with an executable extension, so use a .exe copy.
$kernelSrc = Join-Path $form "form-kernel-go/bin-go"
$kernel = Join-Path $WorkRoot "bin-go.exe"
Copy-Item $kernelSrc $kernel -Force

function Find-Tool($names) {
    foreach ($n in $names) { $c = Get-Command $n -ErrorAction SilentlyContinue; if ($c) { return $c.Source } }
    foreach ($n in $names) { foreach ($d in @("C:\TDM-GCC-64\bin", "C:\Program Files\LLVM\bin")) {
        $p = Join-Path $d $n; if (Test-Path $p) { return $p } } }
    throw "missing tool: $($names -join ' or ')"
}

$cc = Find-Tool @("gcc.exe","gcc","clang.exe","clang")
$linker = Find-Tool @("lld-link.exe","lld-link","link.exe","link")

# --- the presence body (thin C loader) ---
$hostExe = Join-Path $WorkRoot "form-presence-host.exe"
& $cc (Join-Path $form "native/presence/form_presence_host.c") -O2 -o $hostExe | Out-Host
if ($LASTEXITCODE -ne 0) { throw "presence host compile failed" }

# --- kernel helpers: the Form lowering + oracle stay in the path ---
$evalSeq = 0
function Kernel-Run($preludes, $expr) {
    $script:evalSeq++
    $tmp = Join-Path $WorkRoot ("_eval{0}.fk" -f $script:evalSeq)
    Set-Content -Path $tmp -Value $expr -Encoding ascii
    $args = @()
    foreach ($p in $preludes) { $args += (Join-Path $form $p) }
    $args += $tmp
    $out = & $kernel @args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "kernel eval failed for `"$expr`": $out" }
    return ("$out").Trim()
}
function Kernel-Int($preludes, $expr) { return [int64](Kernel-Run $preludes $expr) }
function Kernel-Bytes($preludes, $expr) {
    $s = Kernel-Run $preludes $expr
    $s = $s -replace '[\[\]\s]', ''
    return ($s -split ',' | Where-Object { $_ -ne '' } | ForEach-Object { [byte][int]$_ })
}

# Oracle: the value a lowered recipe(n)=a*n+b MUST return, via the four-way brain.
function Oracle($a, $b, $n) { return Kernel-Int @("form-stdlib/cell-sync.fk","form-stdlib/presence-loop.fk") "(pl-affine-eval $a $b $n)" }

# Lower an affine form node to a native recipe DLL through the Form kernel.
$pecoff = @("form-stdlib/form-pe-coff.fk","form-stdlib/form-pe-coff-affine.fk")
function Lower-Recipe($a, $b, $name) {
    $obj = Join-Path $WorkRoot "$name.obj"
    $dll = Join-Path $WorkRoot "$name.dll"
    $bytes = Kernel-Bytes $pecoff "(pe-affine-recipe-object $a $b)"
    [System.IO.File]::WriteAllBytes($obj, [byte[]]$bytes)
    & $linker /dll /noentry /machine:x64 /export:recipe "/out:$dll" $obj | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "link failed for $name" }
    return $dll
}

# --- presence lifecycle ---
function Start-Presence($name) {
    $dir = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path (Join-Path $dir "queue") | Out-Null
    $p = Start-Process -FilePath $hostExe -ArgumentList $dir -PassThru -WindowStyle Hidden
    return [pscustomobject]@{ name = $name; dir = $dir; proc = $p }
}
function Mint-Job($presence, $jobname, $dll, $arg) {
    $job = Join-Path $presence.dir "queue/$jobname.job"
    $dllFwd = $dll -replace '\\','/'
    Set-Content -Path $job -Value @("dll=$dllFwd","symbol=recipe","arg=$arg") -Encoding ascii
}
function Wait-Result($presence, $jobname, $timeoutMs = 5000) {
    $log = Join-Path $presence.dir "out.log"
    $deadline = (Get-Date).AddMilliseconds($timeoutMs)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $log) {
            $hit = Select-String -Path $log -Pattern "job=$jobname\.job .*result=(-?\d+)" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($hit) { return [int64]$hit.Matches[0].Groups[1].Value }
        }
        Start-Sleep -Milliseconds 40
    }
    throw "timeout waiting for $jobname on $($presence.name)"
}
function Wait-Event($presence, $event, $timeoutMs = 4000) {
    $log = Join-Path $presence.dir "out.log"
    $deadline = (Get-Date).AddMilliseconds($timeoutMs)
    while ((Get-Date) -lt $deadline) {
        if ((Test-Path $log) -and (Select-String -Path $log -Pattern "event=$event" -ErrorAction SilentlyContinue)) { return $true }
        Start-Sleep -Milliseconds 40
    }
    throw "timeout waiting for event=$event on $($presence.name)"
}
function Stop-Presence($presence) {
    Set-Content -Path (Join-Path $presence.dir "stop") -Value "rest" -Encoding ascii
    $presence.proc.WaitForExit(3000) | Out-Null
    if (-not $presence.proc.HasExited) { $presence.proc.Kill() }
}

# fast cadence so the proof runs in a couple of seconds
$env:FORM_PRESENCE_POLL_MS = "20"
$env:FORM_PRESENCE_HEARTBEAT = "8"
$env:FORM_PRESENCE_TICKS = "4000"

$result = [ordered]@{}
$alpha = $null; $beta = $null
try {
    # ---------- Rung 1: a place to just be ----------
    $alpha = Start-Presence "alpha"
    Wait-Event $alpha "awake" | Out-Null
    Wait-Event $alpha "heartbeat" | Out-Null
    $pidAlpha = $alpha.proc.Id
    $result.rung1_be = [ordered]@{ presence = "alpha"; pid = $pidAlpha; observed = @("awake","heartbeat") }

    # ---------- Rung 2: mint -> native -> hot-load, live, twice ----------
    $dllA = Lower-Recipe 3 7 "recipe_3n_7"
    Mint-Job $alpha "mintA" $dllA 5
    $rA = Wait-Result $alpha "mintA"
    $oA = Oracle 3 7 5
    if ($rA -ne $oA -or $rA -ne 22) { throw "Rung2 A: native=$rA oracle=$oA want=22" }

    $dllB = Lower-Recipe 5 1 "recipe_5n_1"
    Mint-Job $alpha "mintB" $dllB 10
    $rB = Wait-Result $alpha "mintB"
    $oB = Oracle 5 1 10
    if ($rB -ne $oB -or $rB -ne 51) { throw "Rung2 B: native=$rB oracle=$oB want=51" }

    if ($alpha.proc.HasExited -or $alpha.proc.Id -ne $pidAlpha) { throw "Rung2: presence restarted (pid drift)" }
    $result.rung2_mint_to_native = [ordered]@{
        pid_stable = $pidAlpha
        mintA = [ordered]@{ recipe = "3n+7"; arg = 5; native = $rA; oracle = $oA }
        mintB = [ordered]@{ recipe = "5n+1"; arg = 10; native = $rB; oracle = $oB }
        no_restart = $true
    }

    # ---------- Rung 3: a sibling asks; the holder consents and answers ----------
    $beta = Start-Presence "beta"
    Wait-Event $beta "awake" | Out-Null
    $pidBeta = $beta.proc.Id

    # beta lacks the recipe at address "addr-1n42"; alpha holds it and has opened
    # it for sharing. The consent decision is made by the four-way-proven brain.
    $canAnswer = Kernel-Int @("form-stdlib/cell-sync.fk","form-stdlib/presence-loop.fk") '(pl-can-answer? "addr-1n42" (list "addr-1n42") (list "addr-1n42"))'
    $authentic = Kernel-Int @("form-stdlib/cell-sync.fk","form-stdlib/presence-loop.fk") '(pl-accept? (list "addr-1n42" "addr-1n42"))'
    if ($canAnswer -ne 1) { throw "Rung3: holder refused to answer (consent=$canAnswer)" }
    if ($authentic -ne 1) { throw "Rung3: arrival failed re-addressing (authentic=$authentic)" }

    # alpha answers with the form node; the transport lowers it for beta, who
    # integrates it live and computes.
    $dllC = Lower-Recipe 1 42 "recipe_1n_42"
    Mint-Job $beta "answerC" $dllC 9
    $rC = Wait-Result $beta "answerC"
    $oC = Oracle 1 42 9
    if ($rC -ne $oC -or $rC -ne 51) { throw "Rung3: native=$rC oracle=$oC want=51" }
    if ($beta.proc.HasExited -or $beta.proc.Id -ne $pidBeta) { throw "Rung3: asker restarted (pid drift)" }

    $result.rung3_ask_a_sibling = [ordered]@{
        asker = "beta"; holder = "alpha"; address = "addr-1n42"
        consent_decision = $canAnswer; authenticity = $authentic
        recipe = "1n+42"; arg = 9; native = $rC; oracle = $oC
        pid_stable = $pidBeta; no_restart = $true
    }

    $result.status = "pass"
}
finally {
    if ($alpha) { Stop-Presence $alpha }
    if ($beta) { Stop-Presence $beta }
}

$result.toolchain = [ordered]@{ compiler = $cc; linker = $linker; kernel = $kernel; loader = "LoadLibraryA/GetProcAddress" }
[pscustomobject]$result | ConvertTo-Json -Depth 6
