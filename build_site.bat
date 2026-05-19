@echo off
cd /d "%~dp0"
python run_update.py --build-site --site-dir site --formats none --lookbacks 7,14,30,90 %*
pause
