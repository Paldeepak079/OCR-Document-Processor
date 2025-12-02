# OCR Extraction and Verification System

This project is a local, privacy-focused OCR solution that extracts text from documents and verifies it against user input. It uses Microsoft's **TrOCR** model for high-accuracy text recognition and **FastAPI** for the backend.

## Features
- **Text Extraction**: Upload an image (ID card, form, etc.) to extract text.
- **Data Verification**: Compare manually entered data against the extracted text to find mismatches.
- **Local Processing**: No cloud services used; all processing happens on your machine.

## Prerequisites
- Python 3.8+
- Internet connection (for first-time model download)

## Installation

1. **Navigate to the project directory**:
   ```bash
   cd "c:/Users/bhauk/Documents/Optical Character Recognition (OCR)"
   ```

2. **Run the setup and start script**:
   Double-click `run_app.bat` or run it from the terminal:
   ```bash
   .\run_app.bat
   ```
   This script will:
   - Create a virtual environment (`venv`)
   - Install necessary dependencies
   - Start the backend server

## Usage

1. **Open the Frontend**:
   Open `frontend/index.html` in your web browser.

2. **Extract Text**:
   - Drag and drop an image or click "Choose File".
   - Click "Extract Text".
   - Wait for the model to process (first time may be slower).

3. **Verify Data**:
   - View the extracted text.
   - Enter data into the "Mapped Fields" section (Name, ID, Date).
   - Click "Verify Data".
   - See the match status and confidence scores.

## Architecture
- **Backend**: Python, FastAPI, Hugging Face Transformers (TrOCR), PyTorch.
- **Frontend**: HTML5, CSS3, Vanilla JavaScript.

## Note on Performance
The TrOCR model is a deep learning model. It requires some RAM and CPU/GPU power. The first run will download the model (~1GB), so please be patient.
