@echo off
echo Building GST Invoice Desktop App...
echo.

echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Building executable...
pyinstaller run.py --name=GSTInvoice --onefile --console --add-data "templates;templates" --add-data "static;static" --hidden-import flask --hidden-import flask_sqlalchemy --hidden-import sqlalchemy --hidden-import weasyprint --hidden-import openpyxl --hidden-import werkzeug --clean --noconfirm

echo.
echo ========================================
echo Build complete!
echo Executable: dist\GSTInvoice.exe
echo.
echo To run: dist\GSTInvoice.exe
echo ========================================
pause