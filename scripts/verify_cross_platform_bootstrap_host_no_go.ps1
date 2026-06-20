param(
    [string]$WorkDir = ""
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $WorkDir) {
    $WorkDir = Join-Path $repo ".cache/bootstrap-host-no-go"
}
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

function Find-Tool($names) {
    foreach ($name in $names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    foreach ($name in $names) {
        foreach ($dir in @("C:\TDM-GCC-64\bin", "C:\Program Files\LLVM\bin")) {
            $path = Join-Path $dir $name
            if (Test-Path $path) { return $path }
        }
    }
    throw "missing tool: $($names -join ' or ')"
}

function Add-U16([System.Collections.Generic.List[byte]]$out, [int]$n) {
    $out.Add([byte]($n -band 255))
    $out.Add([byte](($n -shr 8) -band 255))
}

function Add-U32([System.Collections.Generic.List[byte]]$out, [uint32]$n) {
    $out.Add([byte]($n -band 255))
    $out.Add([byte](($n -shr 8) -band 255))
    $out.Add([byte](($n -shr 16) -band 255))
    $out.Add([byte](($n -shr 24) -band 255))
}

function Add-Bytes([System.Collections.Generic.List[byte]]$out, [byte[]]$bytes) {
    foreach ($b in $bytes) { $out.Add($b) }
}

function New-RecipeObject([byte[]]$code) {
    $out = [System.Collections.Generic.List[byte]]::new()
    $codeOff = 60
    $symOff = $codeOff + $code.Length
    Add-U16 $out 34404
    Add-U16 $out 1
    Add-U32 $out 0
    Add-U32 $out ([uint32]$symOff)
    Add-U32 $out 1
    Add-U16 $out 0
    Add-U16 $out 0
    Add-Bytes $out ([byte[]](46,116,101,120,116,0,0,0))
    Add-U32 $out 0
    Add-U32 $out 0
    Add-U32 $out ([uint32]$code.Length)
    Add-U32 $out ([uint32]$codeOff)
    Add-U32 $out 0
    Add-U32 $out 0
    Add-U16 $out 0
    Add-U16 $out 0
    Add-U32 $out 1615855648
    Add-Bytes $out $code
    Add-Bytes $out ([byte[]](114,101,99,105,112,101,0,0))
    Add-U32 $out 0
    Add-U16 $out 1
    Add-U16 $out 32
    Add-Bytes $out ([byte[]](2,0))
    Add-U32 $out 4
    return $out.ToArray()
}

function Write-RecipeDll($name, [byte[]]$code) {
    $obj = Join-Path $WorkDir "$name.obj"
    $dll = Join-Path $WorkDir "$name.dll"
    [System.IO.File]::WriteAllBytes($obj, (New-RecipeObject $code))
    & $script:Linker /dll /noentry /machine:x64 /export:recipe "/out:$dll" $obj | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "link failed for $name" }
    return $dll
}

function Invoke-Host($exe, $dll, $arg, [switch]$Measure) {
    $old = $env:FORM_BOOTSTRAP_MEASURE
    try {
        if ($Measure) { $env:FORM_BOOTSTRAP_MEASURE = "1" } else { Remove-Item Env:\FORM_BOOTSTRAP_MEASURE -ErrorAction SilentlyContinue }
        $out = & $exe $dll recipe $arg
        if ($LASTEXITCODE -ne 0) { throw "host call failed for $dll arg=$arg" }
        return $out
    } finally {
        if ($null -eq $old) { Remove-Item Env:\FORM_BOOTSTRAP_MEASURE -ErrorAction SilentlyContinue } else { $env:FORM_BOOTSTRAP_MEASURE = $old }
    }
}

$cc = Find-Tool @("gcc.exe", "gcc", "clang.exe", "clang")
$script:Linker = Find-Tool @("lld-link.exe", "lld-link", "link.exe", "link")
$src = Join-Path $repo "form/native/bootstrap/form_bootstrap_host.c"
$exe = Join-Path $WorkDir "form-bootstrap-host.exe"
& $cc $src -O2 -o $exe | Out-Host
if ($LASTEXITCODE -ne 0) { throw "host compile failed" }

$dllA = Write-RecipeDll "recipe_mul3_add7" ([byte[]](72,141,68,73,7,195))
$dllB = Write-RecipeDll "recipe_mul5_add1" ([byte[]](72,141,68,137,1,195))
$dllC = Write-RecipeDll "recipe_add42" ([byte[]](72,141,65,42,195))

$rA = (Invoke-Host $exe $dllA 5).Trim()
$rB = (Invoke-Host $exe $dllB 5).Trim()
$rC = (Invoke-Host $exe $dllC 9).Trim()
if ($rA -ne "22") { throw "recipe A returned $rA, want 22" }
if ($rB -ne "26") { throw "recipe B returned $rB, want 26" }
if ($rC -ne "51") { throw "recipe C returned $rC, want 51" }

$measuredLines = Invoke-Host $exe $dllC 9 -Measure
$measured = @{}
foreach ($line in $measuredLines) {
    $parts = "$line".Split("=", 2)
    if ($parts.Count -eq 2) { $measured[$parts[0]] = $parts[1] }
}
foreach ($key in @("result", "boundary", "primitive", "loader", "load_ns", "resolve_ns", "call_ns", "total_ns")) {
    if (-not $measured.ContainsKey($key)) { throw "missing measured field $key" }
}
if ($measured["result"] -ne "51") { throw "measured result $($measured["result"]), want 51" }
if ($measured["boundary"] -ne "form-native-to-host-os-loader") { throw "wrong boundary $($measured["boundary"])" }
if ($measured["primitive"] -ne "dynamic-library-call") { throw "wrong primitive $($measured["primitive"])" }
if ($measured["loader"] -ne "LoadLibraryA/GetProcAddress") { throw "wrong loader $($measured["loader"])" }

[pscustomobject]@{
    status = "pass"
    host = $exe
    linker = $script:Linker
    compiler = $cc
    recipes = [pscustomobject]@{
        mul3_add7_arg5 = [int]$rA
        mul5_add1_arg5 = [int]$rB
        add42_arg9 = [int]$rC
    }
    measurement = $measured
} | ConvertTo-Json -Depth 5
