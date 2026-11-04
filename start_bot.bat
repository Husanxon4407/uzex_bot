@echo off
rem ============================================================
rem  UZEX bot starter. Double-click this file to run the bot.
rem  - Keep this window open: closing it stops the bot.
rem  - If the bot crashes, it restarts by itself after 5 seconds.
rem  - Only ONE copy of the bot may run at a time (same token).
rem ============================================================
title UZEX bot - running (close this window to stop)
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

if not exist ".env" (
  echo ERROR: the .env file is missing.
  echo Copy .env.example to a new file named .env and put the real keys in it.
  pause
  exit /b 1
)

if not exist "uzex.duckdb" (
  echo Database not found - building it now, about 10 seconds...
  python load_data.py
  if errorlevel 1 (
    echo ERROR: could not build the database. Run: pip install -r requirements.txt
    pause
    exit /b 1
  )
)

:loop
echo.
echo [%date% %time%] Starting the bot...
python bot.py
echo [%date% %time%] The bot stopped. Restarting in 5 seconds... (close this window to stop it)
timeout /t 5 /nobreak >nul
goto loop
