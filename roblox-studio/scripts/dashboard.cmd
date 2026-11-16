@echo off
rem Tableau de bord du studio dans le navigateur (double-clic possible). Fermer cette fenetre arrete le tableau
rem de bord, PAS les productions lancees (elles continuent en arriere-plan).
cd /d "%~dp0.."
call "%~dp0studio.cmd" dashboard %*
if errorlevel 1 pause
