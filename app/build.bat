
@echo off
setlocal

set NAME=PlanBoard
set ENTRY=app\main.py

rmdir /S /Q build 2>NUL
rmdir /S /Q dist 2>NUL
del /Q %NAME%.spec 2>NUL

.\venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed --name "%NAME%" --icon "app\resources\icons\app.ico" --add-data "app\resources;app\resources" "%ENTRY%"

echo EXE: dist\%NAME%.exe
pause
