@echo off
setlocal
chcp 65001 >nul
title Memivo - Intelligent Photo Organization
pushd "%~dp0"
if defined MEMIVO_PYTHON goto memivo_custom
if defined SEGMENTFLOW_PYTHON goto custom
if exist ".venv-spectrum\Scripts\python.exe" goto spectrum_python
if exist ".venv-album\Scripts\python.exe" goto local_album
if exist ".venv\Scripts\python.exe" goto local_venv
where py >nul 2>nul
if not errorlevel 1 goto python_launcher
where python >nul 2>nul
if not errorlevel 1 goto system_python
echo [ERROR] Python was not found. Install Python 3.12 or configure MEMIVO_PYTHON.
set "album_exit=1"
goto finish
:spectrum_python
".venv-spectrum\Scripts\python.exe" "scripts\launch_spectrum.py" %*
goto capture
:memivo_custom
"%MEMIVO_PYTHON%" "scripts\launch_spectrum.py" %*
goto capture
:custom
"%SEGMENTFLOW_PYTHON%" "scripts\launch_spectrum.py" %*
goto capture
:local_album
".venv-album\Scripts\python.exe" "scripts\launch_spectrum.py" %*
goto capture
:local_venv
".venv\Scripts\python.exe" "scripts\launch_spectrum.py" %*
goto capture
:python_launcher
py -3 "scripts\launch_spectrum.py" %*
goto capture
:system_python
python "scripts\launch_spectrum.py" %*
:capture
set "album_exit=%errorlevel%"
:finish
if "%album_exit%"=="0" goto done
echo.
echo Startup failed. See the error above.
if /i "%~1"=="--check" goto done
pause
:done
popd
exit /b %album_exit%
