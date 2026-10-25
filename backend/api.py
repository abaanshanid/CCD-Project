import shutil
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from batch_processor import process_batch


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = BASE_DIR / "uploads"
OUTPUT_ROOT = BASE_DIR / "api_output"

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

SUPPORTED_FORMATS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

BATCHES = {}


app = FastAPI(
    title="Batch Image Processor API",
    description=(
        "Upload and process multiple images using resize, crop, "
        "rotation, flipping, conversion, compression, duplicate "
        "detection and background removal."
    ),
    version="1.0.0"
)


# Allow the future React frontend to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Makes processed images downloadable through /outputs/...
app.mount(
    "/outputs",
    StaticFiles(directory=OUTPUT_ROOT),
    name="outputs"
)


def validate_options(
    width,
    height,
    rotate,
    flip,
    crop,
    output_format,
    quality,
    duplicate_threshold,
    remove_background
):
    if (width is None) != (height is None):
        raise HTTPException(
            status_code=400,
            detail="Width and height must be supplied together."
        )

    if width is not None and width <= 0:
        raise HTTPException(
            status_code=400,
            detail="Width must be greater than zero."
        )

    if height is not None and height <= 0:
        raise HTTPException(
            status_code=400,
            detail="Height must be greater than zero."
        )

    if rotate not in (None, 0, 90, 180, 270):
        raise HTTPException(
            status_code=400,
            detail="Rotate must be 0, 90, 180 or 270."
        )

    if flip not in (None, "horizontal", "vertical"):
        raise HTTPException(
            status_code=400,
            detail="Flip must be horizontal or vertical."
        )

    if crop not in (None, "1:1", "4:3", "16:9"):
        raise HTTPException(
            status_code=400,
            detail="Crop must be 1:1, 4:3 or 16:9."
        )

    if output_format not in ("WEBP", "PNG", "JPEG", "JPG"):
        raise HTTPException(
            status_code=400,
            detail="Output format must be WEBP, PNG, JPEG or JPG."
        )

    if not 1 <= quality <= 100:
        raise HTTPException(
            status_code=400,
            detail="Quality must be between 1 and 100."
        )

    if not 0 <= duplicate_threshold <= 64:
        raise HTTPException(
            status_code=400,
            detail="Duplicate threshold must be between 0 and 64."
        )

    if remove_background and output_format in ("JPEG", "JPG"):
        raise HTTPException(
            status_code=400,
            detail=(
                "JPEG does not support transparency. "
                "Choose PNG or WEBP for background removal."
            )
        )


def create_unique_upload_path(folder, filename):
    """
    Prevent uploaded files with identical names from overwriting
    one another.
    """
    safe_filename = Path(filename).name
    file_path = folder / safe_filename
    counter = 1

    while file_path.exists():
        file_path = folder / (
            f"{Path(safe_filename).stem}_{counter}"
            f"{Path(safe_filename).suffix}"
        )
        counter += 1

    return file_path


@app.get("/")
def root():
    return {
        "message": "Batch Image Processor API is running.",
        "documentation": "/docs"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.post("/batches")
def create_batch(
    files: List[UploadFile] = File(...),

    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    maintain_aspect_ratio: bool = Form(True),

    rotate: Optional[int] = Form(None),
    flip: Optional[str] = Form(None),
    crop: Optional[str] = Form(None),

    remove_background: bool = Form(False),

    output_format: str = Form("WEBP"),
    quality: int = Form(85),
    duplicate_threshold: int = Form(5)
):
    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one image is required."
        )

    output_format = output_format.upper()

    if flip:
        flip = flip.lower()

    validate_options(
        width=width,
        height=height,
        rotate=rotate,
        flip=flip,
        crop=crop,
        output_format=output_format,
        quality=quality,
        duplicate_threshold=duplicate_threshold,
        remove_background=remove_background
    )

    # Validate every file before creating the batch
    for uploaded_file in files:
        if not uploaded_file.filename:
            raise HTTPException(
                status_code=400,
                detail="An uploaded file has no filename."
            )

        extension = Path(
            uploaded_file.filename
        ).suffix.lower()

        if extension not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file: {uploaded_file.filename}. "
                    "Only JPG, JPEG, PNG and WEBP are supported."
                )
            )

    batch_id = uuid4().hex

    upload_folder = UPLOAD_ROOT / batch_id
    output_folder = OUTPUT_ROOT / batch_id

    upload_folder.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir(parents=True, exist_ok=True)

    uploaded_filenames = []

    # Save uploaded images locally
    for uploaded_file in files:
        upload_path = create_unique_upload_path(
            folder=upload_folder,
            filename=uploaded_file.filename
        )

        try:
            with upload_path.open("wb") as destination:
                shutil.copyfileobj(
                    uploaded_file.file,
                    destination
                )

            uploaded_filenames.append(upload_path.name)

        except OSError as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Could not save {uploaded_file.filename}: "
                    f"{error}"
                )
            )

        finally:
            uploaded_file.file.close()

    resize_options = None

    if width is not None and height is not None:
        resize_options = {
            "width": width,
            "height": height,
            "maintain_aspect_ratio": maintain_aspect_ratio
        }

    operations = {
        "resize": resize_options,
        "rotate": rotate,
        "flip": flip,
        "crop": crop,
        "remove_background": remove_background,
        "output_format": output_format,
        "quality": quality,
        "duplicate_threshold": duplicate_threshold
    }

    try:
        batch_result = process_batch(
            input_folder=upload_folder,
            output_folder=output_folder,
            resize=resize_options,
            rotate=rotate,
            flip=flip,
            crop=crop,
            remove_background=remove_background,
            output_format=output_format,
            quality=quality,
            duplicate_threshold=duplicate_threshold
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Batch processing failed: {error}"
        )

    # Add a download URL to each successful result
    for result in batch_result["results"]:
        if result["output_file"]:
            result["download_url"] = (
                f"/outputs/{batch_id}/"
                f"{result['output_file']}"
            )
        else:
            result["download_url"] = None

    response = {
        "batch_id": batch_id,
        "status": (
            "completed"
            if batch_result["failed"] == 0
            else "completed_with_errors"
        ),
        "uploaded_files": uploaded_filenames,
        "operations": operations,
        **batch_result
    }

    # Temporary in-memory storage for local development
    BATCHES[batch_id] = response

    return response


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str):
    if batch_id not in BATCHES:
        raise HTTPException(
            status_code=404,
            detail="Batch not found."
        )

    return BATCHES[batch_id]