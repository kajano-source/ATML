# ATML 1.4.1 installer for Windows (PowerShell).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install.ps1 [-Yes]
param([switch]$Yes)
$ErrorActionPreference = "Stop"
$AtmlVersion = "1.4.1"
$Base = Join-Path $env:LOCALAPPDATA "ATML"
$BinDir = Join-Path $Base "bin"
$Root = Split-Path (Split-Path $MyInvocation.MyCommand.Path -Parent) -Parent
Write-Host "ATML $AtmlVersion installer (Base=$Base)"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "python not found. Install Python 3 from https://www.python.org/downloads/ (tick 'Add to PATH')."
  exit 1
}
New-Item -ItemType Directory -Force -Path $Base, $BinDir | Out-Null

function Copy-Tree($Src, $Dst) {
  if (Test-Path $Src) {
    $items = Get-ChildItem $Src -Force | Measure-Object | Select-Object -ExpandProperty Count
    New-Item -ItemType Directory -Force -Path $Dst | Out-Null
    if ($items -gt 0) { Copy-Item (Join-Path $Src "*") $Dst -Recurse -Force; Write-Host "copied $Src -> $Dst" }
    else { Write-Host "(note) $Src is empty, marker dir created" }
  } else { Write-Host "(skip) $Src not present" }
}

Copy-Tree (Join-Path $Root "compiler") (Join-Path $Base "compiler")
Copy-Tree (Join-Path $Root "runtime")  (Join-Path $Base "runtime")
Copy-Tree (Join-Path $Root "examples") (Join-Path $Base "examples")

@'
@echo off
python "%~dp0..\compiler\atmlc.py" %*
'@ | Set-Content -Encoding Ascii (Join-Path $BinDir "atml.bat")
Write-Host "shim -> $BinDir\atml.bat"

# VS Code extension: .vsix if present, else syntax-only copy.
$vsix = Get-ChildItem $Root -Recurse -Filter *.vsix -ErrorAction SilentlyContinue | Select-Object -First 1
$code = Get-Command code -ErrorAction SilentlyContinue
if ($vsix -and $code) {
  & code --install-extension $vsix.FullName
} elseif (Test-Path (Join-Path $Root "vscode-atml\syntaxes")) {
  $dst = Join-Path $env:USERPROFILE ".vscode\extensions\atml-$AtmlVersion"
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Copy-Item (Join-Path $Root "vscode-atml\syntaxes\*") $dst -Recurse -Force -ErrorAction SilentlyContinue
  Write-Host "syntax-only install -> $dst"
}

# .atml association (per-user; needs no admin for ftype/assoc on most setups).
try {
  & ftype "ATML.Document=`"$BinDir\atml.bat`" `"%1`"" | Out-Null
  & assoc .atml=ATML.Document | Out-Null
  Write-Host "associated .atml -> ATML.Document"
} catch { Write-Host "(warn) file association failed: $_" }

Write-Host "If 'atml' is not on PATH, run: setx PATH `"%PATH%;$BinDir`""
Write-Host "ATML $AtmlVersion installed."
