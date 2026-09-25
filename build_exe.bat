@echo off
echo ====================================
echo  AXIOM - Building Windows EXE
echo ====================================
echo.

call .venv\Scripts\activate

echo [1/3] Installing PyInstaller...
pip install pyinstaller>=6.0 --quiet

echo [2/3] Collecting static files...
python manage.py collectstatic --noinput 2>nul

echo [3/3] Building EXE...
pyinstaller axiom.spec --clean --noconfirm

echo.
echo ====================================
echo  BUILD COMPLETE
echo  EXE location: dist\Axiom\Axiom.exe
echo ====================================
pause