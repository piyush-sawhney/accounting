@echo off
echo.
echo ========================================
echo  GST Invoice Management System
echo ========================================
echo.

REM ========================================
REM CONFIGURATION - Edit these values
REM ========================================

REM Set to "postgres" for PostgreSQL, "sqlite" for SQLite
DB_TYPE=

REM PostgreSQL settings (only used if DB_TYPE=postgres)
set DB_HOST=
set DB_PORT=
set DB_USER=
set DB_PASSWORD=
set DB_NAME=

REM Set to change the secret key (recommended for production)
set SECRET_KEY=dev-secret-key-change-in-production

REM ========================================
REM END CONFIGURATION
REM ========================================

echo Using: %DB_TYPE%
echo.

REM Set database URL based on DB_TYPE
if "%DB_TYPE%"=="postgres" (
    echo Using PostgreSQL...
    set DATABASE_URL=postgresql+psycopg://%DB_USER%:%DB_PASSWORD%@%DB_HOST%:%DB_PORT%/%DB_NAME%
) else (
    echo Using SQLite...
    set DATABASE_URL=sqlite:///gst_invoices.db
)

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

REM Create database if PostgreSQL
if "%DB_TYPE%"=="postgres" (
    echo Creating database if not exists...
    createdb -U %DB_USER% %DB_NAME% 2>nul || echo Database may already exist
)

echo.
echo Starting app at http://127.0.0.1:5000
echo Press Ctrl+C to stop
echo.

python run.py

pause