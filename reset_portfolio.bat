@echo off
echo ========================================
echo    PORTFOLIO ANALYZER - RESET DATA
echo ========================================
echo.
echo This will clear all holdings from your portfolio.
echo.
set /p confirm="Are you sure? (y/N): "
if /i "%confirm%" NEQ "y" (
    echo Cancelled.
    pause
    exit /b
)

echo.
echo Clearing portfolio database...
python clear_database.py

echo.
echo Portfolio has been reset to empty state.
echo You can now add new holdings manually or upload a CSV.
echo.
pause