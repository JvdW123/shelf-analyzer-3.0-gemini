import json
import uuid
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from config import UPLOAD_DIR, OUTPUT_DIR
from analyzer import analyze_shelf
from analyzer_v2 import analyze_shelf_v2
from excel_generator import generate_excel
from metadata_parser import parse_metadata_from_filenames

app = FastAPI(title="Shelf Analyzer 3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/parse-metadata")
async def parse_metadata(filenames: list[str]):
    """Parse metadata from file names without uploading photos."""
    result = parse_metadata_from_filenames(filenames)
    return result


@app.post("/api/analyze")
async def analyze(
    photos: list[UploadFile] = File(...),
    metadata: str = Form(...),
):
    """
    Upload shelf photos and metadata, analyze with Gemini, return SKU data as JSON.
    metadata should be a JSON string with keys: country, city, retailer, store_format, store_name, shelf_location
    """
    # Create a unique session directory
    session_id = str(uuid.uuid4())[:8]
    session_dir = Path(UPLOAD_DIR) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Parse metadata
        meta = json.loads(metadata)

        # Save uploaded photos
        photo_paths = []
        for photo in photos:
            file_path = session_dir / photo.filename
            with open(file_path, "wb") as f:
                content = await photo.read()
                f.write(content)
            photo_paths.append(str(file_path))

        # Analyze with Gemini
        model = meta.pop("model", None)
        use_v2 = meta.pop("use_v2", True)

        if use_v2:
            skus = analyze_shelf_v2(photo_paths, meta, str(session_dir), model=model)
        else:
            skus = analyze_shelf(photo_paths, meta, model=model)

        return {
            "session_id": session_id,
            "sku_count": len(skus),
            "skus": skus,
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up uploaded photos
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)


@app.post("/api/generate-excel")
async def generate_excel_endpoint(data: dict):
    """Generate an Excel file from SKU data and return it for download."""
    skus = data.get("skus", [])
    if not skus:
        raise HTTPException(status_code=400, detail="No SKU data provided")

    session_id = data.get("session_id", str(uuid.uuid4())[:8])
    output_path = str(Path(OUTPUT_DIR) / f"shelf_analysis_{session_id}.xlsx")

    try:
        generate_excel(skus, output_path)
        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"shelf_analysis_{session_id}.xlsx",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
