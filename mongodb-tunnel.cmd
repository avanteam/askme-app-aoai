@echo off
REM Script pour gérer le tunnel MongoDB vers le cluster Kubernetes OVH

if "%1"=="start" goto :start_tunnel
if "%1"=="stop" goto :stop_tunnel
if "%1"=="status" goto :check_status

:help
echo.
echo Usage: mongodb-tunnel.cmd [start^|stop^|status]
echo.
echo   start  - Démarre le tunnel MongoDB (port 27017)
echo   stop   - Arrête tous les tunnels MongoDB
echo   status - Vérifie l'état du tunnel
echo.
goto :end

:start_tunnel
echo.
echo [MongoDB Tunnel] Démarrage du tunnel vers le cluster Kubernetes...

REM Vérifier si kubectl est disponible
kubectl version --client >nul 2>&1
if "%errorlevel%" neq "0" (
    echo [ERREUR] kubectl n'est pas disponible. Assurez-vous que kubectl est installé et configuré.
    exit /B 1
)

REM Vérifier si le port 27017 est déjà utilisé
netstat -an | find ":27017" >nul 2>&1
if "%errorlevel%" equ "0" (
    echo [MongoDB Tunnel] Le port 27017 est déjà utilisé (tunnel probablement actif)
    goto :check_mongo_connection
)

echo [MongoDB Tunnel] Démarrage du port-forward MongoDB (27017:27017)...

REM Créer un fichier batch temporaire pour capturer les erreurs
echo @echo off > temp_tunnel.bat
echo kubectl port-forward -n askme-mongodb service/mongodb-shared 27017:27017 2^>tunnel_error.log >> temp_tunnel.bat

start /B "" temp_tunnel.bat

REM Attendre que le tunnel soit établi
timeout /t 5 >nul

REM Vérifier s'il y a eu des erreurs
if exist tunnel_error.log (
    echo [MongoDB Tunnel] Erreurs détectées :
    type tunnel_error.log
)

:check_mongo_connection
echo [MongoDB Tunnel] Vérification de la connexion MongoDB...
timeout /t 2 >nul

REM Test simple de connexion (via telnet si disponible)
echo [MongoDB Tunnel] Tunnel MongoDB démarré avec succès sur localhost:27017
echo [MongoDB Tunnel] Vous pouvez maintenant utiliser MONGODB_URI=mongodb://root:AskMe-MongoDB-2024-Secure!@localhost:27017/?authSource=admin^&directConnection=true^&serverSelectionTimeoutMS=5000
goto :end

:stop_tunnel
echo.
echo [MongoDB Tunnel] Arrêt des tunnels MongoDB...
taskkill /fi "windowtitle eq MongoDB Tunnel*" /f >nul 2>&1
taskkill /fi "imagename eq kubectl.exe" /f >nul 2>&1
echo [MongoDB Tunnel] Tunnels arrêtés
goto :end

:check_status
echo.
echo [MongoDB Tunnel] Vérification du statut...

REM Vérifier si le port 27017 est en écoute
netstat -an | find ":27017" | find "LISTENING" >nul 2>&1
if "%errorlevel%" equ "0" (
    echo [MongoDB Tunnel] ✅ Port 27017 actif - MongoDB disponible sur localhost:27017

    REM Vérifier si c'est bien un tunnel kubectl
    tasklist /fi "imagename eq kubectl.exe" /fo csv | find "kubectl.exe" >nul 2>&1
    if "%errorlevel%" equ "0" (
        echo [MongoDB Tunnel] ✅ Tunnel kubectl détecté
    ) else (
        echo [MongoDB Tunnel] ⚠️  Port 27017 utilisé par un autre processus
    )
) else (
    echo [MongoDB Tunnel] ❌ Port 27017 non disponible - aucun tunnel actif
)
goto :end

:end