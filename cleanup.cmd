@echo off
REM Script pour nettoyer les processus de développement

echo.
echo [Cleanup] Arrêt des processus de développement...

echo [Cleanup] Arrêt des tunnels MongoDB...
call mongodb-tunnel.cmd stop

echo [Cleanup] Arrêt des serveurs uvicorn...
taskkill /fi "imagename eq python.exe" /fi "windowtitle eq*uvicorn*" /f >nul 2>&1

echo [Cleanup] Nettoyage terminé.
echo.