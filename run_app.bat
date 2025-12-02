@echo off
echo ==========================================
echo OCR System Setup and Run Script
echo ==========================================

cd /d "%~dp0"

if not exist backend\venv (
    echo Creating virtual environment...
    python -m venv backend\venv
)

echo Activating virtual environment...
call backend\venv\Scripts\activate

echo Installing dependencies...
pip install -r backend\requirements.txt
echo Uninstalling any existing incompatible PyTorch...
pip uninstall -y torch torchvision torchaudio
echo Installing Standard PyTorch and OpenMP...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install intel-openmp

echo Checking environment...
python backend\check_env.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Environment check failed. Please check the error messages above.
    echo You may need to install the Visual C++ Redistributable.
    pause
    exit /b 1
)

echo Starting Backend Server...
echo Please open 'frontend/index.html' in your browser to use the app.
echo.
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
