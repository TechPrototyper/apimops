@echo off
REM build_win.bat - PyInstaller build script for Windows
setlocal enabledelayedexpansion

REM Project root is parent of build/
set "PROJECT_ROOT=%~dp0.."
set "BUILD_ROOT=%USERPROFILE%\apimops_build"
set "VENV_DIR=%BUILD_ROOT%\.venv"
set "BUILD_DIR=%BUILD_ROOT%\build"
set "DIST_DIR=%BUILD_ROOT%\dist"

REM Ensure directories exist
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

REM Ensure Chocolatey is installed
where choco >nul 2>&1
if errorlevel 1 (
    echo Chocolatey not found! Installing Chocolatey...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
    if errorlevel 1 (
        echo Failed to install Chocolatey!
        exit /b 1
    )
    echo.
    echo Chocolatey was just installed. Please close and reopen your terminal, then rerun this script.
    exit /b 0
)

REM Ensure Git is installed
where git >nul 2>&1
if errorlevel 1 (
    echo Git not found! Installing via Chocolatey...
    choco install git -y
)

REM Remove existing venv if present
if exist "%VENV_DIR%" (
    echo Removing existing virtual environment...
    rmdir /s /q "%VENV_DIR%"
)

REM Create new venv with python3.12
where python3.12 >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 not found! Trying python...
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python not found! Please install Python 3.12.
        exit /b 1
    )
    python -m venv "%VENV_DIR%"
) else (
    python3.12 -m venv "%VENV_DIR%"
)
if errorlevel 1 (
    echo Failed to create virtual environment
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment
    exit /b 1
)

REM Upgrade pip
python -m pip install --upgrade pip

REM Install requirements
pip install -r "%PROJECT_ROOT%\scripts\setup\requirements.txt"
pip install -r "%PROJECT_ROOT%\scripts\transfer\requirements.txt"

REM Clean up old build/dist
if exist "%BUILD_DIR%" (
    rmdir /s /q "%BUILD_DIR%"
    mkdir "%BUILD_DIR%"
)
if exist "%DIST_DIR%" (
    rmdir /s /q "%DIST_DIR%"
    mkdir "%DIST_DIR%"
)

REM Build using spec files from build/
cd /d "%PROJECT_ROOT%\build"
pyinstaller --clean --distpath "%DIST_DIR%" --workpath "%BUILD_DIR%" setup.spec
pyinstaller --clean --distpath "%DIST_DIR%" --workpath "%BUILD_DIR%" transfer.spec

deactivate
echo Executables created in %DIST_DIR%:
dir "%DIST_DIR%"

REM Copy config.yaml if it exists in project root
if exist "%PROJECT_ROOT%\config.yaml" (
    copy "%PROJECT_ROOT%\config.yaml" "%DIST_DIR%\config.yaml"
)

REM Also copy to binaries dir for consistency
if exist "%DIST_DIR%\transfer.exe" (
    if not exist "%PROJECT_ROOT%\binaries\v6.0.2\win-x64\publisher" mkdir "%PROJECT_ROOT%\binaries\v6.0.2\win-x64\publisher"
)

echo Done.
