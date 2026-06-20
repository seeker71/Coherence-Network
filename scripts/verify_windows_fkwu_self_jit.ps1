<#
Verify the Windows fkwu self-JIT runtime floor.

This script uses Go and clang only as build/proof carriers to emit and compile
the current Form-authored fkc-emit-jit witness. The acceptance check strips the
runtime PATH before executing the generated binary, proving the hot fkwu
self-JIT path does not call Go, clang, LLVM, or any local oracle at runtime.
#>
[CmdletBinding()]
param(
    [string]$Go = "go",
    [string]$Clang = "",
    [string]$LlvmObjdump = "",
    [switch]$KeepTemp
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

function Resolve-OptionalTool {
    param(
        [string]$Requested,
        [string[]]$Names,
        [string[]]$Fallbacks
    )

    try {
        return Resolve-Tool -Requested $Requested -Names $Names -Fallbacks $Fallbacks
    } catch {
        return ""
    }
}

function Find-MarkerIndex {
    param(
        [string[]]$Lines,
        [string]$Marker
    )

    for ($i = 0; $i -lt $Lines.Length; $i++) {
        if ($Lines[$i] -eq $Marker) {
            return $i
        }
    }
    return -1
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$goPath = Resolve-Tool -Requested $Go -Names @("go.exe", "go") -Fallbacks @("C:\Program Files\Go\bin\go.exe")
$clangPath = Resolve-Tool -Requested $Clang -Names @("clang.exe", "clang") -Fallbacks @("C:\Program Files\LLVM\bin\clang.exe")
$objdumpPath = Resolve-OptionalTool -Requested $LlvmObjdump -Names @("llvm-objdump.exe", "llvm-objdump") -Fallbacks @("C:\Program Files\LLVM\bin\llvm-objdump.exe")
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

$work = Join-Path ([System.IO.Path]::GetTempPath()) ("fkwu-self-jit-win-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null

try {
    $goKernel = Join-Path $work "form-kernel-go.exe"
    Push-Location (Join-Path $repoRoot "form\form-kernel-go")
    try {
        & $goPath build -o $goKernel .
        if ($LASTEXITCODE -ne 0) {
            throw "go build failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }

    $driver = Join-Path $work "fkwu-self-jit-driver.fk"
    $stdlib = Join-Path $repoRoot "form\form-stdlib"
    $body = [System.Text.StringBuilder]::new()
    foreach ($file in @("minimal-surface.fk", "hati-os-kernel.fk", "hati-os-kernel-emit.fk")) {
        [void]$body.AppendLine([System.IO.File]::ReadAllText((Join-Path $stdlib $file), $utf8NoBom))
    }
    [void]$body.AppendLine(@'
(do
  (let fibc (fk-if (fk-le (fk-arg) (fk-lit 1)) (fk-arg)
                   (fk-add (fk-call 0 (fk-sub (fk-arg) (fk-lit 1)))
                           (fk-call 0 (fk-sub (fk-arg) (fk-lit 2))))))
  (print "==JIT==")
  (print (fkc-emit-jit (list fibc)))
  (print "==END==")
  0)
'@)
    [System.IO.File]::WriteAllText($driver, $body.ToString(), $utf8NoBom)

    $emitOut = Join-Path $work "emit.out"
    $emitErr = Join-Path $work "emit.err"
    & $goKernel $driver 1>$emitOut 2>$emitErr
    if ($LASTEXITCODE -ne 0) {
        $stderr = Get-Content -Raw -ErrorAction SilentlyContinue $emitErr
        throw "Form JIT emission failed with exit code $LASTEXITCODE`n$stderr"
    }

    $lines = Get-Content -Encoding UTF8 $emitOut
    $start = Find-MarkerIndex -Lines $lines -Marker "==JIT=="
    $end = Find-MarkerIndex -Lines $lines -Marker "==END=="
    if ($start -lt 0 -or $end -le $start) {
        throw "Unable to extract fkc-emit-jit C witness from $emitOut"
    }

    $jitC = Join-Path $work "fkwu-self-jit.c"
    [System.IO.File]::WriteAllText($jitC, (($lines[($start + 1)..($end - 1)]) -join "`n"), $utf8NoBom)

    $jitExe = Join-Path $work "fkwu-self-jit.exe"
    $clangOut = & $clangPath -O2 -Wno-error=implicit-function-declaration -Wno-implicit-function-declaration -Wno-incompatible-library-redeclaration -o $jitExe $jitC 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "clang witness build failed with exit code $LASTEXITCODE`n$($clangOut -join "`n")"
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

        $cold = @(& $jitExe 28)
        if ($LASTEXITCODE -ne 0) {
            throw "cold fkwu self-JIT executable failed with exit code $LASTEXITCODE"
        }
        $hot = @(& $jitExe 28 50)
        if ($LASTEXITCODE -ne 0) {
            throw "hot fkwu self-JIT executable failed with exit code $LASTEXITCODE"
        }
    } finally {
        $env:PATH = $oldPath
    }

    $coldValue = [string]$cold[0]
    $hotValue = [string]$hot[0]
    $njit = [int]$hot[-1]
    if ($coldValue -ne "317811" -or $hotValue -ne "317811" -or $njit -le 0) {
        throw "self-JIT proof failed: cold=$coldValue hot=$hotValue njit=$njit"
    }

    Write-Host "PASS windows-fkwu-self-jit cold=$coldValue hot=$hotValue njit=$njit"
    Write-Host "PASS runtime-toolchain-free path=$runtimePath go=absent clang=absent llvm_objdump=absent"
    Write-Host "FLOOR target=windows-x86_64 alias=windows-amd64 runtime=fkwu-self-jit-no-runtime-toolchain bootstrap_pe_coff=form-native-pending"
    Write-Host "BUILD_CARRIER go=$goPath"
    Write-Host "BUILD_ORACLE clang=$clangPath"

    if ($objdumpPath) {
        $disasm = Join-Path $work "fkwu-self-jit.disasm.txt"
        & $objdumpPath -d $jitExe 1>$disasm 2>$null
        if ($LASTEXITCODE -eq 0) {
            $bytes = (Get-Item -LiteralPath $disasm).Length
            Write-Host "LLVM_ORACLE llvm_objdump=$objdumpPath disassembly_bytes=$bytes"
        } else {
            Write-Host "LLVM_ORACLE llvm_objdump=$objdumpPath disassembly=unavailable"
        }
    } else {
        Write-Host "LLVM_ORACLE llvm_objdump=unavailable"
    }

    if ($KeepTemp) {
        Write-Host "TEMP_KEEP path=$work"
    }
} finally {
    if (-not $KeepTemp -and (Test-Path -LiteralPath $work)) {
        $resolvedWork = (Resolve-Path -LiteralPath $work).Path
        $tempRoot = ([System.IO.Path]::GetTempPath()).TrimEnd("\")
        if ($resolvedWork.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedWork -Recurse -Force
        } else {
            Write-Warning "Refusing to remove unexpected temp path: $resolvedWork"
        }
    }
}
