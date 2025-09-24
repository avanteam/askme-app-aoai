@echo off

echo.
echo [MongoDB] Démarrage du tunnel Kubernetes en arrière-plan...
echo.

REM Lancer le tunnel MongoDB en arrière-plan dans une nouvelle fenêtre
start "MongoDB Tunnel" cmd /k "kubectl port-forward -n askme-mongodb service/mongodb-shared 27017:27017"

echo [MongoDB] Tunnel lancé dans une nouvelle fenêtre.
echo [MongoDB] Attente de l'établissement du tunnel...
timeout /t 5 /nobreak >nul

REM Vérifier si le port 27017 est disponible
netstat -an | find ":27017" | find "LISTENING" >nul 2>&1
if "%errorlevel%" equ "0" (
    echo [MongoDB] ✅ Tunnel MongoDB disponible sur localhost:27017
) else (
    echo [MongoDB] ⚠️  Tunnel en cours d'établissement... (vérifiez la fenêtre MongoDB Tunnel)
)

echo.
echo Restoring backend python packages
echo.
call python -m pip install -r ..\..\requirements.txt
if "%errorlevel%" neq "0" (
    echo Failed to restore backend python packages
    exit /B %errorlevel%
)

echo.
echo Restoring frontend npm packages
echo.
cd ..\..\frontend
call npm install
if "%errorlevel%" neq "0" (
    echo Failed to restore frontend npm packages
    exit /B %errorlevel%
)

echo.
echo Building frontend
echo.
call npm run build
if "%errorlevel%" neq "0" (
    echo Failed to build frontend
    exit /B %errorlevel%
)

echo.
echo Starting backend
echo.
cd ..
start http://127.0.0.1:5007
call python -m uvicorn app:app  --port 5007 --reload
if "%errorlevel%" neq "0" (    
    echo Failed to start backend    
    exit /B %errorlevel%    
) 
