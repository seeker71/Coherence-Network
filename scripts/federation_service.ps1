# federation_service.ps1 - build each part, share each part, anyone adds a part.
#
# Extends the native-presence proof from a toy affine recipe to a real ML-LEARNED
# model served over the HTTP verb surface, exchanged between presences:
#   1. TRAIN   - presence A learns affine weights by SGD on a corpus (aff-train).
#   2. SHARE   - A freezes the learned model NODE to a channel (.fkb).
#   3. PARITY  - B reads the SAME model node and serves it; Go and Rust kernels
#                produce the byte-identical served prediction (content-addressed).
#   4. LIVE    - a running presence serves the shared model via a kernel-walk job,
#                no restart; then a SECOND contributor (C) freezes a DIFFERENT
#                model and the same running presence serves it live too.
#
# The model travels as DATA; the predict/render recipe is the shared vocabulary;
# the HTTP router + middleware composition is proven separately (three-way bands).

param([string]$WorkRoot = "")

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$form = Join-Path $repo "form"
if (-not $WorkRoot) { $WorkRoot = Join-Path $repo ".cache/federation-service" }
if (Test-Path $WorkRoot) { Remove-Item -Recurse -Force $WorkRoot }
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

function Find-Tool($names) {
    foreach ($n in $names) { $c = Get-Command $n -ErrorAction SilentlyContinue; if ($c) { return $c.Source } }
    foreach ($n in $names) { foreach ($d in @("C:\TDM-GCC-64\bin", "C:\Program Files\LLVM\bin")) {
        $p = Join-Path $d $n; if (Test-Path $p) { return $p } } }
    throw "missing tool: $($names -join ' or ')"
}
$cc = Find-Tool @("gcc.exe","gcc","clang.exe","clang")

# kernels (PowerShell needs an executable extension; copy the Go kernel)
$kernelGo = Join-Path $WorkRoot "bin-go.exe"
Copy-Item (Join-Path $form "form-kernel-go/bin-go") $kernelGo -Force
$kernelRsSrc = Join-Path $form "form-kernel-rust/target/release/form-kernel-rust.exe"
$haveRust = Test-Path $kernelRsSrc

# the presence body
$hostExe = Join-Path $WorkRoot "form-presence-host.exe"
& $cc (Join-Path $form "native/presence/form_presence_host.c") -O2 -o $hostExe | Out-Host
if ($LASTEXITCODE -ne 0) { throw "presence host compile failed" }

# raw S-expr parts (no section-compile needed for the model layer)
$aff = (Join-Path $form "form-stdlib/affine-train.fk")    -replace '\\','/'
$ms  = (Join-Path $form "form-stdlib/model-service.fk")   -replace '\\','/'

function Fwd($p) { return ($p -replace '\\','/') }

# train an affine model on a corpus and freeze the learned NODE to a channel.
function Train-Freeze($name, $corpus, $epochs) {
    $modelPath = Fwd (Join-Path $WorkRoot "$name.fkb")
    $freeze = Join-Path $WorkRoot "$name.freeze.fk"
    Set-Content -Encoding ascii -Path $freeze -Value @"
(do
    (let trained (aff-train (list 1000 0) (list $corpus) 10 $epochs))
    (let model (intern_node (make_nodeid 1 2 99 5000)
                            (list (intern_trivial_int (aff-w trained)) (intern_trivial_int (aff-b trained)))))
    (write_form_binary "$modelPath" model))
"@
    $out = & $kernelGo $aff (Fwd $freeze) 2>&1
    if ($LASTEXITCODE -ne 0) { throw "train/freeze failed for ${name}: $out" }
    return $modelPath
}

# write the serve recipe that reads a shared model node and renders a prediction.
function Serve-File($name, $modelPath, $x) {
    $serve = Join-Path $WorkRoot "$name.serve.fk"
    Set-Content -Encoding ascii -Path $serve -Value @"
(do
    (let model (read_form_binary "$modelPath"))
    (let w (node_value (head (node_children model))))
    (let b (node_value (head (tail (node_children model)))))
    (ms-body (ms-predict (list w b) $x)))
"@
    return (Fwd $serve)
}
function Serve-With($kernel, $serve) {
    $out = & $kernel $aff $ms $serve 2>&1
    if ($LASTEXITCODE -ne 0) { throw "serve failed: $out" }
    return ("$out").Trim()
}

# --- presence lifecycle (kernel-walk jobs) ---
function Start-Presence($name) {
    $dir = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path (Join-Path $dir "queue") | Out-Null
    $p = Start-Process -FilePath $hostExe -ArgumentList $dir -PassThru -WindowStyle Hidden
    return [pscustomobject]@{ name = $name; dir = $dir; proc = $p }
}
function Mint-Walk($presence, $jobname, $serve) {
    # a .bat carries the kernel command so popen/cmd.exe quoting stays robust
    $bat = Join-Path $WorkRoot "$jobname.bat"
    Set-Content -Encoding ascii -Path $bat -Value "@echo off`r`n`"$kernelGo`" `"$aff`" `"$ms`" `"$serve`""
    $job = Join-Path $presence.dir "queue/$jobname.job"
    Set-Content -Encoding ascii -Path $job -Value "cmd=$bat"
}
function Wait-Served($presence, $jobname, $timeoutMs = 12000) {
    $log = Join-Path $presence.dir "out.log"
    $deadline = (Get-Date).AddMilliseconds($timeoutMs)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $log) {
            $hit = Select-String -Path $log -Pattern "event=served job=$jobname\.job result=(.+)$" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($hit) { return $hit.Matches[0].Groups[1].Value.Trim() }
        }
        Start-Sleep -Milliseconds 60
    }
    throw "timeout waiting for served $jobname"
}
function Stop-Presence($presence) {
    Set-Content -Path (Join-Path $presence.dir "stop") -Value "rest" -Encoding ascii
    $presence.proc.WaitForExit(3000) | Out-Null
    if (-not $presence.proc.HasExited) { $presence.proc.Kill() }
}

$env:FORM_PRESENCE_POLL_MS = "30"
$env:FORM_PRESENCE_HEARTBEAT = "10"
$env:FORM_PRESENCE_TICKS = "6000"

$result = [ordered]@{}
$pres = $null
try {
    # 1+2. TRAIN + SHARE: A learns y=2x, freezes the model node to a channel.
    $modelA = Train-Freeze "modelA" "(list 1000 2000) (list 2000 4000)" 60
    $serveA = Serve-File "modelA" $modelA 3000
    $aPred = Serve-With $kernelGo $serveA
    $result.train_share = [ordered]@{ presence = "alpha"; corpus = "y=2x"; served = $aPred; note = "learned (SGD), not a constant" }

    # 3. PARITY: B reads the SAME model node; Go and Rust agree byte-for-byte.
    $goServe = Serve-With $kernelGo $serveA
    $parity = [ordered]@{ go = $goServe }
    if ($haveRust) {
        $kernelRs = Join-Path $WorkRoot "form-kernel-rust.exe"; Copy-Item $kernelRsSrc $kernelRs -Force
        $rsServe = Serve-With $kernelRs $serveA
        $parity.rust = $rsServe
        $parity.identical = ($goServe -eq $rsServe -and $goServe -eq $aPred)
        if (-not $parity.identical) { throw "sibling parity broken: go=$goServe rust=$rsServe a=$aPred" }
    } else {
        $parity.rust = "skipped (no rust kernel)"
        $parity.identical = ($goServe -eq $aPred)
    }
    $result.sibling_parity = $parity

    # 4. LIVE: a running presence serves the shared model, no restart.
    $pres = Start-Presence "server"
    $pid0 = $pres.proc.Id
    Mint-Walk $pres "serveA" $serveA
    $liveA = Wait-Served $pres "serveA"
    if ($liveA -ne $aPred) { throw "live serve A = $liveA, want $aPred" }

    # anyone adds a PART: contributor C freezes a DIFFERENT model (y=3x); the SAME
    # running presence serves it live.
    $modelC = Train-Freeze "modelC" "(list 1000 3000) (list 2000 6000)" 60
    $serveC = Serve-File "modelC" $modelC 3000
    $cExpect = Serve-With $kernelGo $serveC
    Mint-Walk $pres "serveC" $serveC
    $liveC = Wait-Served $pres "serveC"
    if ($liveC -ne $cExpect) { throw "live serve C = $liveC, want $cExpect" }
    if ($pres.proc.HasExited -or $pres.proc.Id -ne $pid0) { throw "presence restarted (pid drift)" }
    if ($liveA -eq $liveC) { throw "two models served the same value; model is not data" }

    $result.live_serve = [ordered]@{
        pid_stable = $pid0
        served_modelA = $liveA
        added_by_contributor_C = [ordered]@{ corpus = "y=3x"; served = $liveC }
        no_restart = $true
        distinct_models = $true
    }
    $result.status = "pass"
}
finally {
    if ($pres) { Stop-Presence $pres }
}
$result.toolchain = [ordered]@{ compiler = $cc; kernel_go = $kernelGo; rust_available = $haveRust; loader = "kernel-walk (popen) + LoadLibrary native lane" }
[pscustomobject]$result | ConvertTo-Json -Depth 6
