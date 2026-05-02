@echo off
chcp 65001 >nul
echo ================================
echo   Open Music - ????EXE
echo ================================
echo.

REM ?? Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [??] ???? Python????? Python 3.8+
    pause
    exit /b 1
)

REM ?? PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [??] ???? PyInstaller...
    pip install pyinstaller
)

REM ????
echo [??] ??????...
pip install PySide6 pygame pillow numpy pywin32

REM ??
echo [??] ???? EXE...
pyinstaller --onedir --windowed --name "OpenMusic" --add-data "Open Music.png;." --add-data "dist/OpenMusic;dist/OpenMusic" --hidden-import PySide6.QtSvg --hidden-import PySide6.QtXml --hidden-import win32com OpenMusic.py

echo.
echo ================================
echo   ?????
echo   EXE ??: dist\OpenMusic\OpenMusic.exe
echo ================================
pause
