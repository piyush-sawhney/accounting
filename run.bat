@echo off
echo.
echo ========================================
echo  GST Invoice Management System
echo ========================================
echo.

REM ========================================
REM CONFIGURATION - Edit these values
REM ========================================

set DB_HOST=localhost
set DB_PORT=5432
set DB_USER=postgres
set DB_PASSWORD=your_password
set DB_NAME=gst_invoices

REM Set to change the secret key (recommended for production)
set SECRET_KEY=dev-secret-key-change-in-production

REM ========================================
REM END CONFIGURATION
REM ========================================

set DATABASE_URL=postgresql+psycopg://%DB_USER%:%DB_PASSWORD%@%DB_HOST%:%DB_PORT%/%DB_NAME%
echo Using PostgreSQL: %DB_NAME%@%DB_HOST%:%DB_PORT%
echo.

REM Create virtual environment if not exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Install dependencies if needed
echo Installing dependencies...
pip install -r requirements.txt
echo.

echo.
echo Starting app at http://127.0.0.1:5000
echo Press Ctrl+C to stop
echo.

python run.py

pause