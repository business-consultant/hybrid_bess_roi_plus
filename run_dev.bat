@echo off
title Bluence APM (dev)
setlocal

rem === Lanzador de desarrollo: arranca la app con el venv del proyecto ===
rem Independiente de VS Code / agente. Si el servidor se cae, se relanza solo.

cd /d "%~dp0"

set "PORT=8502"
set "PYTHONPATH=%~dp0src"

rem Si ya hay una instancia escuchando, solo abre el navegador y sale.
netstat -ano | findstr ":%PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo   Bluence APM ya esta en ejecucion en el puerto %PORT%.
    echo   Abriendo navegador...
    start "" http://localhost:%PORT%
    timeout /t 2 >nul
    exit /b
)

echo.
echo   ========================================
echo     Bluence APM  -  http://localhost:%PORT%
echo   ========================================
echo     Cierra esta ventana para detener.
echo     Si el servidor cae, se reinicia solo.
echo   ========================================
echo.

start "" http://localhost:%PORT%

:loop
".venv\Scripts\python.exe" -m streamlit run "src\bess_simulator\ui\app.py" ^
    --server.headless true ^
    --server.port %PORT% ^
    --server.runOnSave false ^
    --browser.gatherUsageStats false

echo.
echo   [%date% %time%] El servidor se ha detenido. Reiniciando en 3s... (Ctrl+C para salir)
timeout /t 3 >nul
goto loop

endlocal
