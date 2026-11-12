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

Step "1/7 Python 3.11+ (3.12 conseillé)"
function FindPy {
    foreach ($v in @("3.13", "3.12", "3.11")) {
        if (Has "py") { & py "-$v" -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { return @("py", "-$v") } }
    }
    return $null
}
$pyCmd = FindPy
if (-not $pyCmd) {
    Write-Host "Aucun Python >= 3.11 (une version plus ancienne peut exister, elle ne convient pas)." -ForegroundColor Yellow
    WingetInstall "Python.Python.3.12" "Python 3.12"
    $pyCmd = FindPy
    if (-not $pyCmd) { $pyCmd = @("py", "-3.12") }
}
Write-Host "Python utilisé : $($pyCmd -join ' ')"

Step "2/7 FFmpeg (avec libass et libx264)"
if (Has "ffmpeg") { ffmpeg -hide_banner -version | Select-Object -First 1 } else { WingetInstall "Gyan.FFmpeg" "FFmpeg" }

Step "3/7 Blender (binaire officiel, utilise votre carte graphique)"
$blender = Get-ChildItem "C:\Program Files\Blender Foundation\Blender*\blender.exe" -ErrorAction SilentlyContinue | Select-Object -Last 1
if ($blender) { Write-Host "Blender trouvé : $($blender.FullName)" } else { WingetInstall "BlenderFoundation.Blender" "Blender" }

Step "4/7 Voix de test espeak-ng"
$espeak = Test-Path "C:\Program Files\eSpeak NG\espeak-ng.exe"
if ($espeak -or (Has "espeak-ng")) { Write-Host "espeak-ng trouvé" } else {
    Write-Host "Installer espeak-ng avec le fichier .msi officiel : https://github.com/espeak-ng/espeak-ng/releases (espeak-ng.msi)" -ForegroundColor Yellow
}

Step "5/7 Dépendances Python"
$py = $pyCmd[0]; $pyArgs = @($pyCmd[1..($pyCmd.Length - 1)])
& $py @pyArgs -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "pip a échoué : fermez/rouvrez PowerShell puis relancez ce script." -ForegroundColor Yellow }

Step "6/7 Git (mises à jour avec git pull) et Codex (agents : écriture, mise en scène, critiques)"
if (Has "git") { git --version } else { WingetInstall "Git.Git" "Git" }
if (Has "codex") { Write-Host "Codex trouvé : $((Get-Command codex).Source)" } else {
    $ans = Read-Host "Installer Codex (nécessite Node.js, connexion avec votre compte ChatGPT ensuite) ? [o/N]"
    if ($ans -match '^[oOyY]') {
        if (-not (Has "npm")) { WingetInstall "OpenJS.NodeJS.LTS" "Node.js LTS"; $env:Path += ";C:\Program Files\nodejs" }
        Write-Host "npm install -g @openai/codex"
        npm install -g @openai/codex
        Write-Host "Ensuite, dans un NOUVEAU PowerShell :  codex login" -ForegroundColor Yellow
    } else { Write-Host "Sans Codex, seules les étapes automatiques (rendu, montage, contrôles) tournent." }
}

Step "7/7 Réglages locaux et raccourci du tableau de bord"
if (-not (Test-Path "config\local.toml")) { Copy-Item "config\local.example.toml" "config\local.toml"; Write-Host "config\local.toml créé (vos réglages, jamais écrasés par une mise à jour)" }
try {
    $desk = [Environment]::GetFolderPath("Desktop")
    $sh = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desk "Studio TikTok 3D.lnk"))
    $sh.TargetPath = (Resolve-Path "scripts\dashboard.cmd").Path
    $sh.WorkingDirectory = (Get-Location).Path
    $sh.Description = "Tableau de bord du studio (navigateur)"
    $sh.Save()
    Write-Host "Raccourci « Studio TikTok 3D » créé sur le Bureau (double-clic = tableau de bord)."
} catch { Write-Host "Raccourci non créé : lancez scripts\dashboard.cmd" -ForegroundColor Yellow }

Write-Host "`nIMPORTANT : fermez et rouvrez PowerShell pour que les nouveaux programmes soient dans le PATH," -ForegroundColor Green
Write-Host "puis lancez le diagnostic :  scripts\studio.cmd doctor" -ForegroundColor Green
Write-Host "et le tableau de bord   :  scripts\dashboard.cmd   (ou le raccourci du Bureau)" -ForegroundColor Green
