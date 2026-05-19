@echo off
cd /d "%~dp0"
python run_update.py --build-site --site-dir site --formats none --lookbacks 7,14,30,90
if errorlevel 1 pause & exit /b 1
git add data/history site/data site/index.html site/.nojekyll
git commit -m "Update coconut weather dashboard data"
git push
pause
