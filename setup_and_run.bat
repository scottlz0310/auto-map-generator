@echo off
setlocal enabledelayedexpansion

title Auto Map Generator

echo ========================================================
echo   Auto Map Generator - Setup ^& Launch
echo ========================================================
echo.

:: 1. Check uv
where uv >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [Info] uv is not installed. Installing uv automatically...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if %ERRORLEVEL% NEQ 0 (
        echo [Error] Failed to install uv. Please check your internet connection.
        pause
        exit /b 1
    )
    set "PATH=%USERPROFILE%\.cargo\bin;%LOCALAPPDATA%\bin;%PATH%"
)

:: 2. Sync dependencies
echo [1/2] Synchronizing dependencies with uv sync...
uv sync
if %ERRORLEVEL% NEQ 0 (
    echo [Error] Failed to sync dependencies.
    pause
    exit /b 1
)

:: 3. Launch GUI
echo [2/2] Launching GUI application...
echo.
uv run python -m app.gui

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] An error occurred while running the application.
    pause
)
