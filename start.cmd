@echo off

echo.
echo [MongoDB] Démarrage du tunnel Kubernetes...
echo.
call mongodb-tunnel.cmd start
if "%errorlevel%" neq "0" (
    echo [AVERTISSEMENT] Impossible de démarrer le tunnel MongoDB. Vérifiez votre connexion Kubernetes.
) else (
    echo [MongoDB] Attente de l'établissement du tunnel...
    timeout /t 5 /nobreak >nul
    echo [MongoDB] Tunnel prêt !
)

echo.
echo Restoring backend python packages
echo.
call python -m pip install -r requirements.txt
if "%errorlevel%" neq "0" (
    echo Failed to restore backend python packages
    exit /B %errorlevel%
)

echo.
echo Restoring frontend npm packages
echo.
cd frontend
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
