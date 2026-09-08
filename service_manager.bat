@echo off
REM Web LLM Bridge - Windows Service Manager
REM Requires: NSSM (Non-Sucking Service Manager) - https://nssm.cc/
REM Run as Administrator

set SERVICE_NAME=WebLLMBridge
set PYTHON_EXE=%~dp0\.venv\Scripts\python.exe
set MAIN_SCRIPT=%~dp0\main.py
set WORK_DIR=%~dp0
set NSSM=D:\nssm-2.24-103-gdee49fc\win64\nssm.exe

if not exist "%NSSM%" (
    echo NSSM not found at %NSSM%
    echo Please ensure NSSM is installed at D:\nssm-2.24-103-gdee49fc\win64\nssm.exe
    exit /b 1
)

if "%1"=="" (
    echo Usage: %0 ^<command^>
    echo Commands:
    echo   install    - Install as Windows service
    echo   uninstall  - Remove Windows service
    echo   start      - Start service
    echo   stop       - Stop service
    echo   restart    - Restart service
    echo   status     - Show service status
    echo   logs       - Show recent logs
    exit /b 0
)

if "%1"=="install" (
    echo Installing service %SERVICE_NAME%...
    "%NSSM%" install %SERVICE_NAME% "%PYTHON_EXE%" "%MAIN_SCRIPT%"
    "%NSSM%" set %SERVICE_NAME% AppDirectory "%WORK_DIR%"
    "%NSSM%" set %SERVICE_NAME% AppStdout "%WORK_DIR%logs\service_stdout.log"
    "%NSSM%" set %SERVICE_NAME% AppStderr "%WORK_DIR%logs\service_stderr.log"
    "%NSSM%" set %SERVICE_NAME% AppRotateFiles 1
    "%NSSM%" set %SERVICE_NAME% AppRotateOnline 1
    "%NSSM%" set %SERVICE_NAME% Description "Web LLM Bridge - Virtual LLM API Gateway"
    "%NSSM%" set %SERVICE_NAME% Start SERVICE_AUTO_START
    echo Service installed. Run '%0 start' to start.
    exit /b 0
)

if "%1"=="uninstall" (
    echo Stopping service...
    "%NSSM%" stop %SERVICE_NAME%
    timeout /t 3 >nul
    echo Uninstalling service %SERVICE_NAME%...
    "%NSSM%" remove %SERVICE_NAME% confirm
    echo Service uninstalled.
    exit /b 0
)

if "%1"=="start" (
    echo Starting service %SERVICE_NAME%...
    "%NSSM%" start %SERVICE_NAME%
    timeout /t 2 >nul
    "%NSSM%" status %SERVICE_NAME%
    exit /b 0
)

if "%1"=="stop" (
    echo Stopping service %SERVICE_NAME%...
    "%NSSM%" stop %SERVICE_NAME%
    timeout /t 3 >nul
    "%NSSM%" status %SERVICE_NAME%
    exit /b 0
)

if "%1"=="restart" (
    echo Restarting service %SERVICE_NAME%...
    "%NSSM%" stop %SERVICE_NAME%
    timeout /t 3 >nul
    "%NSSM%" start %SERVICE_NAME%
    timeout /t 2 >nul
    "%NSSM%" status %SERVICE_NAME%
    exit /b 0
)

if "%1"=="status" (
    "%NSSM%" status %SERVICE_NAME%
    exit /b 0
)

if "%1"=="logs" (
    echo === Service Stdout ===
    type "%WORK_DIR%logs\service_stdout.log" 2>nul || echo (no stdout log)
    echo.
    echo === Service Stderr ===
    type "%WORK_DIR%logs\service_stderr.log" 2>nul || echo (no stderr log)
    echo.
    echo === Application Log ===
    type "%WORK_DIR%logs\bridge.log" 2>nul || echo (no bridge log)
    echo.
    echo === Audit Log (last 20 lines) ===
    powershell -Command "Get-Content '%WORK_DIR%logs\audit.log' -Tail 20" 2>nul || echo (no audit log)
    exit /b 0
)

echo Unknown command: %1
exit /b 1