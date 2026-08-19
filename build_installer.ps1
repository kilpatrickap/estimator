# build_installer.ps1
# Complete one-click packaging script for Estimator Pro

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Estimator Pro - Build & Packaging Pipeline " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 1. Clean previous build folders
Write-Host "`n[1/4] Cleaning previous build folders..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "Output") { Remove-Item -Recurse -Force "Output" }

# 2. Run unit tests
Write-Host "`n[2/4] Running automated tests..." -ForegroundColor Yellow
python -m pytest PyTest/
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Unit tests failed! Aborting build." -ForegroundColor Red
    exit 1
}

# 3. Compile Python executable with PyInstaller
Write-Host "`n[3/4] Building standalone executable with PyInstaller..." -ForegroundColor Yellow
python -m PyInstaller Estimator_Pro.spec --clean
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ PyInstaller compilation failed!" -ForegroundColor Red
    exit 1
}

# 4. Compile Inno Setup installer
Write-Host "`n[4/4] Compiling Windows setup installer with Inno Setup..." -ForegroundColor Yellow
$isccPath = "C:\Program Files (x86)\Inno Setup 6\iscc.exe"
if (-not (Test-Path $isccPath)) {
    # Check alternate 64-bit location
    $isccPath = "C:\Program Files\Inno Setup 6\iscc.exe"
}

if (Test-Path $isccPath) {
    & $isccPath installer_script.iss
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n=============================================" -ForegroundColor Green
        Write-Host "  BUILD SUCCESSFUL!" -ForegroundColor Green
        Write-Host " Installer ready at: Output\EstimatorPro_Setup.exe" -ForegroundColor Green
        Write-Host "=============================================" -ForegroundColor Green
        Write-Host "`n IMPORTANT FOR GITHUB RELEASES:" -ForegroundColor Yellow
        Write-Host " -> Upload ONLY: Output\EstimatorPro_Setup.exe" -ForegroundColor Cyan
        Write-Host " -> DO NOT upload dist\Estimator_Pro.exe (it is an uninstalled raw binary)." -ForegroundColor Red
        Write-Host "=============================================" -ForegroundColor Green
    } else {
        Write-Host "❌ Inno Setup compilation failed!" -ForegroundColor Red
    }
} else {
    Write-Host "⚠️ Inno Setup (iscc.exe) not found. Compiled .exe is available in dist\Estimator_Pro.exe." -ForegroundColor DarkYellow
    Write-Host "Install Inno Setup 6 (winget install JRSoftware.InnoSetup) to generate Output\EstimatorPro_Setup.exe." -ForegroundColor DarkYellow
}
