@echo off
setlocal
set "NEXORA_ROOT=%~dp0"
if not defined NEXORA_CLOUD_API_PORT set "NEXORA_CLOUD_API_PORT=8002"
if not defined NEXORA_LOCAL_API_PORT set "NEXORA_LOCAL_API_PORT=8765"

if not exist "%NEXORA_ROOT%.venv\Scripts\python.exe" (
  echo The project virtual environment is missing at .venv\Scripts\python.exe.
  pause
  exit /b 1
)

netstat -ano -p tcp | findstr /R /C:":%NEXORA_CLOUD_API_PORT% .*LISTENING" >nul
if errorlevel 1 start "NEXORA Cloud API" "%ComSpec%" /k "cd /d ""%NEXORA_ROOT%"" && ""%NEXORA_ROOT%.venv\Scripts\python.exe"" -m uvicorn api.public_server:app --host 127.0.0.1 --port %NEXORA_CLOUD_API_PORT%"

netstat -ano -p tcp | findstr /R /C:":%NEXORA_LOCAL_API_PORT% .*LISTENING" >nul
if errorlevel 1 start "NEXORA Windows API" "%ComSpec%" /k "cd /d ""%NEXORA_ROOT%"" && ""%NEXORA_ROOT%.venv\Scripts\python.exe"" -m uvicorn api.server:app --host 127.0.0.1 --port %NEXORA_LOCAL_API_PORT%"

netstat -ano -p tcp | findstr /R /C:":5173 .*LISTENING" >nul
if errorlevel 1 start "NEXORA Frontend" "%ComSpec%" /k "cd /d ""%NEXORA_ROOT%frontend"" && npm run dev -- --host 127.0.0.1"

echo NEXORA local services are starting. Open http://localhost:5173 after Vite is ready.
echo MongoDB must already be running. Keep the service windows open.
endlocal
