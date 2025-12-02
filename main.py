from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
import json
from rapidfuzz import fuzz
from ocr_engine import ocr_engine

app = FastAPI(title="OCR Extraction and Verification API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "OCR API is running"}

@app.post("/extract")
async def extract_text(
    file: UploadFile = File(...),
    doc_type: str = Form("handwritten") # Default to handwritten
):
    if not (file.content_type.startswith("image/") or file.content_type == "application/pdf"):
        raise HTTPException(status_code=400, detail="File must be an image or PDF")
    
    content = await file.read()
    is_pdf = file.content_type == "application/pdf"
    result = ocr_engine.extract_text(content, doc_type, is_pdf)
    
    return result

@app.post("/verify")
async def verify_data(
    file: UploadFile = File(...), 
    submitted_data: str = Form(...)
):
    content = await file.read()
    # We re-extract using the same default or maybe passed type? 
    # For now, let's assume handwritten for verification re-check or just use the text if we stored it.
    # But to be stateless, we re-extract.
    extraction_result = ocr_engine.extract_text(content, "handwritten")
    extracted_text = extraction_result["raw_text"]
    
    try:
        submitted_dict = json.loads(submitted_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in submitted_data")

    matches = {}
    
    for key, user_value in submitted_dict.items():
        # Find the best match in the extracted text
        # Partial ratio is good for finding the substring
        score = fuzz.partial_ratio(str(user_value).lower(), extracted_text.lower())
        
        matches[key] = score

    return {
        "matches": matches,
        "original_extracted_text": extracted_text
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
