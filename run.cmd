@echo off
setlocal

REM NSE Swing Lab - one-shot setup + run
REM Installs Python deps into the active python, then starts the Streamlit app
REM and a Cloudflare quick tunnel. Copy the trycloudflare URL it prints and
REM paste it as the UPSTREAM_URL secret in Cloudflare Pages.

set "PROJECT_DIR=%USERPROFILE%\Documents\nse-swing-lab"
set "PY=python"

echo === [1/4] Checking Python ===
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo Python not found on PATH. Install Python 3.11+ from python.org or Microsoft Store and re-run.
  pause
  exit /b 1
)
%PY% --version

echo.
echo === [2/4] Installing Python dependencies ===
%PY% -m pip install --upgrade pip >nul
%PY% -m pip install pandas numpy streamlit plotly pyarrow requests python-dotenv tqdm
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)

echo.
echo === [3/4] Starting Streamlit on port 8501 ===
cd /d "%PROJECT_DIR%"
start "NSE Swing Lab - Streamlit" cmd /k "%PY% -m streamlit run src\nse_swing_lab\app.py --server.port 8501 --server.address 0.0.0.0"

echo Waiting 6s for Streamlit to come up...
timeout /t 6 /nobreak >nul

echo.
echo === [4/4] Starting Cloudflare quick tunnel ===
where cloudflared >nul 2>&1
if errorlevel 1 (
  if exist "C:\Tools\cloudflared.exe" (
    set "CF=C:\Tools\cloudflared.exe"
  ) else (
    echo cloudflared not found. Downloading to C:\Tools\cloudflared.exe ...
    if not exist "C:\Tools" mkdir "C:\Tools" >nul 2>&1
    curl -L -o "C:\Tools\cloudflared.exe" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    set "CF=C:\Tools\cloudflared.exe"
  )
) else (
  set "CF=cloudflared"
)

echo.
echo ============================================================
echo Streamlit is up at: http://localhost:8501
echo Now starting the tunnel. Copy the https://*.trycloudflare.com
echo URL it prints below and paste it into:
echo   wrangler pages secret put UPSTREAM_URL --project-name nse-swing-lab
echo Then redeploy:
echo   cd /d "%PROJECT_DIR%" ^&^& wrangler pages deploy . --project-name nse-swing-lab --commit-dirty=true
echo ============================================================
echo.

"%CF%" tunnel --url http://localhost:8501

endlocal
