@echo off
rem Build a standalone ATML GUI installer exe with PyInstaller (onefile).
rem Requires: pip install pyinstaller  &&  Inno Setup for the full installer.
rem Usage: installer\windows\build-exe.bat
cd /d "%~dp0..\.."
pyinstaller --onefile --windowed --name atml-setup-1.2.0 installer\gui_installer.py
echo Done: dist\atml-setup-1.2.0.exe
echo Optional next step: iscc installer\windows\atml.iss
