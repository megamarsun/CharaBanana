@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ====================================
REM Configuration
REM ====================================

set APP_NAME=CharaBanana

REM このバッチファイルが置いてあるディレクトリ (最後に\がつく)
set SCRIPT_DIR=%~dp0

REM メインのPythonスクリプト
set MAIN_PY=%SCRIPT_DIR%CharaBanana.py

REM アプリ用アイコン (なくてもOK)
set ICON_FILE=%SCRIPT_DIR%banana.ico

REM 配布用の初期データ（APIキーなど入っていないクリーンなやつ）
set TEMPLATE_DIR=%SCRIPT_DIR%data_template

REM PyInstallerの出力先
set DIST_ROOT=%SCRIPT_DIR%dist
set DIST_DIR=%DIST_ROOT%\%APP_NAME%

REM ====================================
REM Checks
REM ====================================

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pyinstaller not found. Run: pip install pyinstaller
    goto END
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python not found in PATH.
    goto END
)

if not exist "%MAIN_PY%" (
    echo [ERROR] %MAIN_PY% not found.
    goto END
)

if not exist "%TEMPLATE_DIR%" (
    echo [ERROR] %TEMPLATE_DIR% not found.
    echo Please create data_template/ with clean public JSON.
    goto END
)

REM certifi の CA証明書パスを Python から取得
for /f "delims=" %%i in ('python -c "import certifi,sys;print(certifi.where())"') do set CERTIFI_PEM=%%i

if not exist "!CERTIFI_PEM!" (
    echo [ERROR] Could not locate certifi CA bundle.
    echo Try: pip install certifi
    goto END
)

echo [INFO] certifi pem: !CERTIFI_PEM!

REM ====================================
REM Clean previous build
REM ====================================

echo [INFO] Cleaning old build/dist/spec...
if exist "%SCRIPT_DIR%build" rd /s /q "%SCRIPT_DIR%build"
if exist "%SCRIPT_DIR%dist" rd /s /q "%SCRIPT_DIR%dist"
if exist "%SCRIPT_DIR%%APP_NAME%.spec" del /f /q "%SCRIPT_DIR%%APP_NAME%.spec"

REM ====================================
REM Build with PyInstaller
REM ====================================

echo [INFO] Running PyInstaller...

if exist "%ICON_FILE%" (
    pyinstaller --clean --noconsole --onedir --name "%APP_NAME%" --icon "%ICON_FILE%" ^
        --add-data "!CERTIFI_PEM!;certifi" ^
        "%MAIN_PY%"
) else (
    pyinstaller --clean --noconsole --onedir --name "%APP_NAME%" ^
        --add-data "!CERTIFI_PEM!;certifi" ^
        "%MAIN_PY%"
)

if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    goto END
)

if not exist "%DIST_DIR%" (
    echo [ERROR] Dist folder "%DIST_DIR%" not found after build.
    goto END
)

REM ====================================
REM Copy template data into dist
REM ====================================

echo [INFO] Copying template data into dist...

xcopy "%TEMPLATE_DIR%\*" "%DIST_DIR%\" /E /I /Y >nul

REM 念のため outputs/ があることを保証
if not exist "%DIST_DIR%\outputs" (
    mkdir "%DIST_DIR%\outputs"
)

echo.
echo ===================================
echo ✅ Build complete!
echo Distributable folder:
echo   %DIST_DIR%
echo.
echo このフォルダごと配布してOKです。
echo data_work はコピーされていません。（あなたの秘密データは入っていません）
echo ===================================
echo.

:END
endlocal
pause
