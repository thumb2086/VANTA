# build_webgl.ps1 — Export VANTA to WebGL and prepare for Cloudflare deployment
# Usage: .\scripts\build_webgl.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ClientDir   = Join-Path $ProjectRoot "client"
$ExportCfg   = Join-Path $ClientDir "export_presets.cfg"
$BuildDir    = Join-Path $ProjectRoot "webgl_build"

Write-Host "=== VANTA WebGL Build ===" -ForegroundColor Cyan

# ── 1. Check Godot 4.4+ ────────────────────────────────────────────

function Find-Godot {
    # Check common install paths
    $candidates = @(
        "godot",
        "godot4",
        "$env:LOCALAPPDATA\Godot\Godot_v4*.exe",
        "$env:ProgramFiles\Godot\Godot_v4*.exe",
        "C:\Godot\Godot_v4*.exe"
    )
    foreach ($c in $candidates) {
        $found = Get-Command $c -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    # Glob search
    foreach ($pattern in @("$env:LOCALAPPDATA\Godot\*.exe", "C:\Godot\*.exe")) {
        $matches = Get-ChildItem $pattern -ErrorAction SilentlyContinue |
                   Where-Object { $_.Name -match "4\.[4-9]|4\.\d{2,}" } |
                   Sort-Object Name -Descending
        if ($matches.Count -gt 0) { return $matches[0].FullName }
    }
    return $null
}

$godot = Find-Godot
if (-not $godot) {
    Write-Error "Godot 4.4+ not found. Install from https://godotengine.org/download/ and ensure it is on PATH."
    exit 1
}

Write-Host "[OK] Godot: $godot" -ForegroundColor Green

# Verify version
$verOutput = & $godot --version 2>&1
Write-Host "     Version: $verOutput"

# ── 2. Ensure export_presets.cfg exists ─────────────────────────────

if (-not (Test-Path $ExportCfg)) {
    Write-Host "[..] Creating export_presets.cfg" -ForegroundColor Yellow
    $presetContent = @'
[preset.0]

name="Web"
platform="Web"
runnable=true
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""

export_path="webgl_build/index.html"
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false

[preset.0.options]

custom_template/debug=""
custom_template/release=""
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/export_icon=true
html/custom_html_shell=""
html/head_include=""
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
html/experimental_virtual_keyboard=false
progressive_web_app/enabled=false
progressive_web_app/offline_page=""
progressive_web_app/display=1
progressive_web_app/orientation=0
progressive_web_app/icon_144x144=""
progressive_web_app/icon_180x180=""
progressive_web_app/icon_512x512=""
progressive_web_app/background_color=Color(0, 0, 0, 1)
'@
    Set-Content -Path $ExportCfg -Value $presetContent -Encoding UTF8
    Write-Host "[OK] export_presets.cfg created" -ForegroundColor Green
} else {
    Write-Host "[OK] export_presets.cfg already exists" -ForegroundColor Green
}

# ── 3. Create build output directory ────────────────────────────────

if (-not (Test-Path $BuildDir)) {
    New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
    Write-Host "[OK] Created $BuildDir" -ForegroundColor Green
}

# ── 4. Export to WebGL ──────────────────────────────────────────────

Write-Host "[..] Exporting to WebGL..." -ForegroundColor Yellow
Push-Location $ClientDir
& $godot --headless --export-release "Web" (Join-Path $BuildDir "index.html")
$exportExit = $LASTEXITCODE
Pop-Location

if ($exportExit -ne 0) {
    Write-Error "Godot export failed with exit code $exportExit"
    exit $exportExit
}
Write-Host "[OK] WebGL export complete" -ForegroundColor Green

# ── 5. Verify wrangler.static.jsonc exists ──────────────────────────

$StaticWrangler = Join-Path $ProjectRoot "workers\wrangler.static.jsonc"
if (Test-Path $StaticWrangler) {
    Write-Host "[OK] wrangler.static.jsonc found for static deployment" -ForegroundColor Green
} else {
    Write-Host "[!!] workers/wrangler.static.jsonc not found — create it for Cloudflare static serving" -ForegroundColor Yellow
}

# ── 6. Summary ──────────────────────────────────────────────────────

$files = Get-ChildItem $BuildDir -Recurse -File
$totalSize = ($files | Measure-Object Length -Sum).Sum / 1MB

Write-Host ""
Write-Host "=== Build Complete ===" -ForegroundColor Cyan
Write-Host "Output:     $BuildDir"
Write-Host "Files:      $($files.Count)"
Write-Host "Total size: $([math]::Round($totalSize, 2)) MB"
Write-Host ""
Write-Host "To deploy to Cloudflare:" -ForegroundColor Yellow
Write-Host "  cd $ProjectRoot\workers"
Write-Host "  npx wrangler deploy -c wrangler.static.jsonc"
