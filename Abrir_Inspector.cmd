@echo off
cd /d "%~dp0"
py -3 -m inspector.gui
if errorlevel 1 (
 echo Para instalar Python, visitar python.org.
 pause
)
