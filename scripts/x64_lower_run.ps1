# x64_lower_run.ps1 - execution conviction for the clang-free x86-64 lowering.
#
# form-lower-x64.fk lowers an op-tagged expression tree to x64 machine BYTES (a
# Form recipe, no clang); form-pe-coff.fk wraps them as a COFF object exporting
# `recipe`; lld-link links the DLL; the bootstrap host loads and calls it. The
# recipe's machine code is 100% Form-emitted -- clang/gcc never touch it. (gcc
# builds only the tiny host exe, the named host surface; lld-link is the linker
# carrier, not a compiler or assembler.) The binary RUNS and returns the
# program's value -- the witness ladder's deepest gate, per form-to-asm.form.

param([string]$WorkRoot = "")
$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$form = Join-Path $repo "form"
if (-not $WorkRoot) { $WorkRoot = Join-Path $repo ".cache/x64-lower-run" }
if (Test-Path $WorkRoot) { Remove-Item -Recurse -Force $WorkRoot }
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

function Find-Tool($names) {
    foreach ($n in $names) { $c = Get-Command $n -ErrorAction SilentlyContinue; if ($c) { return $c.Source } }
    foreach ($n in $names) { foreach ($d in @("C:\TDM-GCC-64\bin", "C:\Program Files\LLVM\bin")) {
        $p = Join-Path $d $n; if (Test-Path $p) { return $p } } }
    throw "missing tool: $($names -join ' or ')"
}
$cc = Find-Tool @("gcc.exe","gcc","clang.exe","clang")
$linker = Find-Tool @("lld-link.exe","lld-link","link.exe","link")

$kernel = Join-Path $WorkRoot "bin-go.exe"
Copy-Item (Join-Path $form "form-kernel-go/bin-go") $kernel -Force
$hostExe = Join-Path $WorkRoot "form-bootstrap-host.exe"
& $cc (Join-Path $form "native/bootstrap/form_bootstrap_host.c") -O2 -o $hostExe | Out-Host
if ($LASTEXITCODE -ne 0) { throw "host compile failed" }

$preludes = @(
    (Join-Path $form "form-stdlib/form-pe-coff.fk"),
    (Join-Path $form "form-stdlib/form-asm-x64.fk"),
    (Join-Path $form "form-stdlib/form-lower-x64.fk"))
$seq = 0
# lower the tree, wrap the COFF object, link a DLL exporting `recipe` -- zero clang
function Lower-Link($name, $progExpr, $root) {
    $script:seq++
    $eval = Join-Path $WorkRoot ("_lx{0}.fk" -f $script:seq)
    Set-Content -Encoding ascii -Path $eval -Value "(pe-recipe-object (lx-compile-fn $progExpr $root))"
    $out = & $kernel @preludes $eval 2>&1
    if ($LASTEXITCODE -ne 0) { throw "lower failed for ${name}: $out" }
    $bytes = ("$out") -replace '[\[\]\s]', '' -split ',' | Where-Object { $_ -ne '' } | ForEach-Object { [byte][int]$_ }
    $obj = Join-Path $WorkRoot "$name.obj"; $dll = Join-Path $WorkRoot "$name.dll"
    [System.IO.File]::WriteAllBytes($obj, [byte[]]$bytes)
    & $linker /dll /noentry /machine:x64 "/export:recipe" "/out:$dll" $obj | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "link failed for $name" }
    return $dll
}
function Run($dll, $arg) {
    $out = & $hostExe $dll recipe $arg
    if ($LASTEXITCODE -ne 0) { throw "host call failed" }
    return [int64](("$out").Trim())
}

# each: name, tree (indexed rows), root, arg, expected (computed independently)
$cases = @(
    @{ n="affine_3n_7";  p="(list (list 2) (list 1 3) (list 5 0 1) (list 1 7) (list 3 2 3))"; r=4; arg=5;   want=22  },
    @{ n="affine_3n_7b"; p="(list (list 2) (list 1 3) (list 5 0 1) (list 1 7) (list 3 2 3))"; r=4; arg=100; want=307 },
    @{ n="sq_plus_n";    p="(list (list 2) (list 5 0 0) (list 2) (list 3 1 2))";             r=3; arg=9;   want=90  },  # n*n + n
    @{ n="n_plus_n_x_n"; p="(list (list 2) (list 3 0 0) (list 2) (list 5 1 2))";             r=3; arg=5;   want=50  },  # (n+n)*n
    @{ n="sq_minus_3";   p="(list (list 2) (list 5 0 0) (list 1 3) (list 4 1 2))";           r=3; arg=6;   want=33  }   # n*n - 3
)
$results = @()
foreach ($c in $cases) {
    $dll = Lower-Link $c.n $c.p $c.r
    $got = Run $dll $c.arg
    if ($got -ne $c.want) { throw "$($c.n): recipe($($c.arg)) = $got, want $($c.want)" }
    $results += [ordered]@{ recipe=$c.n; arg=$c.arg; native=$got; want=$c.want }
}
[pscustomobject]@{
    status = "pass"
    note = "x86-64 machine code lowered by Form (form-lower-x64), zero clang in the code path"
    toolchain = [ordered]@{ recipe_codegen="form-lower-x64.fk (Form, no clang)"; host_cc=$cc; linker=$linker; loader="LoadLibraryA/GetProcAddress" }
    runs = $results
} | ConvertTo-Json -Depth 6
