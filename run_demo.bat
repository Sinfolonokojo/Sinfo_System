@echo off
echo ============================================================
echo   ELASTIC BAND TRADING BOT - DEMO MODE
echo ============================================================
echo.
echo Strategy: FVG (Fair Value Gap)
echo Phase: Challenge (10%% profit target, 5%% max DD)
echo Symbols: EURUSD, GBPUSD, USDJPY
echo Timeframe: M15
echo.
echo IMPORTANT: Replace credentials below with your MT5 demo account
echo ============================================================
echo.
pause

REM Replace these with your MT5 demo credentials
set MT5_ACCOUNT=YOUR_ACCOUNT_NUMBER
set MT5_PASSWORD=YOUR_PASSWORD
set MT5_SERVER=YOUR_SERVER_NAME

cd bot
python main.py --account %MT5_ACCOUNT% --password %MT5_PASSWORD% --server %MT5_SERVER% --name "FVG_DEMO"

pause
