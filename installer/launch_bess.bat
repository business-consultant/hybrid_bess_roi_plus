@echo off
title BESS Simulator
setlocal

set "BESS_ROOT=%~dp0"
set "BESS_PORTABLE=1"
set "PYTHONPATH=%BESS_ROOT%src"

:: Comprobar si ya hay una instancia en el puerto 8501
netstat -ano | findstr ":8501" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo   BESS Simulator ya esta en ejecucion.
    echo   Abriendo navegador...
    echo.
    start "" http://localhost:8501
    timeout /t 3 >nul
    exit /b
)

echo.
echo   ========================================
echo     BESS Simulator
echo     http://localhost:8501
echo   ========================================
echo     Cierra esta ventana para detener
echo   ========================================
echo.
start "" http://localhost:8501

"%BESS_ROOT%python\python.exe" -m streamlit run "%BESS_ROOT%src\bess_simulator\ui\app.py" ^
    --server.headless true ^
    --server.port 8501 ^
    --browser.gatherUsageStats false

pause
endlocal
