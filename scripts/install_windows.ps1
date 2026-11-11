# Installation native Windows 10/11 (PowerShell). Lancer depuis la racine du dépôt :
#   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
# N'utilise que winget (gestionnaire officiel de Microsoft) et PyPI. Chaque commande est affichée avant exécution.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Step($msg) { Write-Host "`n== $msg ==" -ForegroundColor Cyan }
function Has($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function WingetInstall($id, $label) {
    Write-Host "winget install --id $id -e --accept-source-agreements --accept-package-agreements"
    winget install --id $id -e --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { Write-Host "  -> échec ou déjà installé ($label). Voir WINDOWS.md pour l'installation manuelle." -ForegroundColor Yellow }
}

if (-not (Has "winget")) {
    Write-Host "winget est introuvable : installer « App Installer » depuis le Microsoft Store, puis relancer ce script." -ForegroundColor Red
    exit 1
}

Step "1/5 Python 3.12"
if (Has "py") { py -3 --version } elseif (Has "python") { python --version } else { WingetInstall "Python.Python.3.12" "Python" }

Step "2/5 FFmpeg (avec libass et libx264)"
if (Has "ffmpeg") { ffmpeg -hide_banner -version | Select-Object -First 1 } else { WingetInstall "Gyan.FFmpeg" "FFmpeg" }

Step "3/5 Blender (binaire officiel, utilise votre carte graphique)"
$blender = Get-ChildItem "C:\Program Files\Blender Foundation\Blender*\blender.exe" -ErrorAction SilentlyContinue | Select-Object -Last 1
if ($blender) { Write-Host "Blender trouvé : $($blender.FullName)" } else { WingetInstall "BlenderFoundation.Blender" "Blender" }

Step "4/5 Voix de test espeak-ng"
$espeak = Test-Path "C:\Program Files\eSpeak NG\espeak-ng.exe"
if ($espeak -or (Has "espeak-ng")) { Write-Host "espeak-ng trouvé" } else {
    Write-Host "Installer espeak-ng avec le fichier .msi officiel : https://github.com/espeak-ng/espeak-ng/releases (espeak-ng.msi)" -ForegroundColor Yellow
}

Step "5/5 Dépendances Python"
if (Has "py") { $py = "py"; $pyArgs = @("-3") } else { $py = "python"; $pyArgs = @() }
& $py @pyArgs -m pip install -r requirements.txt

Write-Host "`nIMPORTANT : fermez et rouvrez PowerShell pour que les nouveaux programmes soient dans le PATH," -ForegroundColor Green
Write-Host "puis lancez le diagnostic :  scripts\studio.cmd doctor" -ForegroundColor Green
