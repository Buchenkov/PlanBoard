@echo off
setlocal
set NAME=TaskPlanner
set ENTRY=app\main.py

cd /d %~dp0

rmdir /S /Q build 2>NUL
rmdir /S /Q dist 2>NUL
del /Q %NAME%.spec 2>NUL

".\venv\Scripts\pyinstaller.exe" noconfirm ^
  name %NAME% ^
  onefile ^
  windowed ^
  add-data "app\resources;app\resources" ^
  %ENTRY%

echo.
echo Сборка завершена. EXE: dist\%NAME%.exe
pause
endlocal