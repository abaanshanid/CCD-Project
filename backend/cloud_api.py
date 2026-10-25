import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
from uuid import uuid4
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel, Field

INPUT_BUCKET = os.environ["INPUT_BUCKET"]
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
TABLE_NAME = os.environ["TABLE_NAME"]
QUEUE_URL = os.environ["QUEUE_URL"]

s3 = boto3.client("s3")
sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

OUTPUT_EXTENSIONS = {"WEBP": ".webp", "PNG": ".png", "JPEG": ".jpg", "JPG": ".jpg"}


app = FastAPI(
    title="CCD Batch Image Processor API",
    description=(
        "Create image batches, upload images directly to S3, "
        "start processing and check batch progress."
    ),
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImageUploadRequest(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"


class ResizeOptions(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    maintain_aspect_ratio: bool = True


class OperationOptions(BaseModel):
    resize: Optional[ResizeOptions] = None
    rotate: Optional[int] = None
    flip: Optional[str] = None
    crop: Optional[str] = None
    remove_background: bool = False
    output_format: str = "WEBP"
    quality: int = Field(default=85, ge=1, le=100)
    duplicate_threshold: int = Field(default=5, ge=0, le=64)


class CreateBatchRequest(BaseModel):
    files: List[ImageUploadRequest] = Field(min_length=1, max_length=50)
    operations: OperationOptions = Field(default_factory=OperationOptions)


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def expiration_timestamp():
    return int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())


def json_default(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)

        return float(value)

    raise TypeError(
        f"Object of type {type(value).__name__} " "is not JSON serializable"
    )


def clean_filename(filename):
    filename = filename.replace("\\", "/")
    return Path(filename).name


def validate_operations(operations):
    operations.output_format = operations.output_format.upper()

    if operations.flip:
        operations.flip = operations.flip.lower()

    if operations.rotate not in (None, 0, 90, 180, 270):
        raise HTTPException(status_code=400, detail="Rotate must be 0, 90, 180 or 270.")

    if operations.flip not in (None, "horizontal", "vertical"):
        raise HTTPException(
            status_code=400, detail="Flip must be horizontal or vertical."
        )

    if operations.crop not in (None, "1:1", "4:3", "16:9"):
        raise HTTPException(status_code=400, detail="Crop must be 1:1, 4:3 or 16:9.")

    if operations.output_format not in OUTPUT_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail=("Output format must be WEBP, PNG, " "JPEG or JPG.")
        )

    if operations.remove_background and operations.output_format in ("JPEG", "JPG"):
        raise HTTPException(
            status_code=400,
            detail=(
                "JPEG does not support transparency. "
                "Use PNG or WEBP for background removal."
            ),
        )

    return operations


def get_batch_record(batch_id):
    response = table.get_item(Key={"batchId": batch_id, "itemId": "BATCH"})

    return response.get("Item")


def get_batch_images(batch_id):
    response = table.query(
        KeyConditionExpression=(
            Key("batchId").eq(batch_id) & Key("itemId").begins_with("IMAGE#")
        )
    )

    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression=(
                Key("batchId").eq(batch_id) & Key("itemId").begins_with("IMAGE#")
            ),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )

        items.extend(response.get("Items", []))

    return sorted(items, key=lambda item: item.get("createdAt", ""))


def output_download_url(output_key):
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": OUTPUT_BUCKET, "Key": output_key},
        ExpiresIn=3600,
    )


def calculate_batch_status(images):
    if not images:
        return "EMPTY"

    statuses = [image.get("status", "UNKNOWN") for image in images]

    completed = statuses.count("COMPLETED")
    failed = statuses.count("FAILED")

    if completed + failed == len(images):
        if failed == 0:
            return "COMPLETED"

        if completed == 0:
            return "FAILED"

        return "COMPLETED_WITH_ERRORS"

    if "PROCESSING" in statuses:
        return "PROCESSING"

    if "QUEUED" in statuses:
        return "QUEUED"

    return "AWAITING_UPLOAD"


@app.get("/")
def root():
    return {"message": "CCD cloud API is running.", "documentation": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/batches", status_code=201)
def create_batch(request: CreateBatchRequest):
    operations = validate_operations(request.operations)

    batch_id = uuid4().hex
    created_at = current_timestamp()
    expires_at = expiration_timestamp()

    operation_data = operations.model_dump(exclude_none=True)

    upload_items = []
    database_items = []

    used_filenames = set()

    for uploaded_file in request.files:
        filename = clean_filename(uploaded_file.filename)

        if not filename:
            raise HTTPException(
                status_code=400, detail="Every image must have a filename."
            )

        extension = Path(filename).suffix.lower()

        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported image: {filename}. "
                    "Only JPG, JPEG, PNG and WEBP are supported."
                ),
            )

        filename_key = filename.lower()

        if filename_key in used_filenames:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Duplicate filename in request: {filename}. "
                    "Rename one of the files before uploading."
                ),
            )

        used_filenames.add(filename_key)

        image_id = uuid4().hex
        input_key = f"{batch_id}/originals/" f"{image_id}{extension}"

        content_type = uploaded_file.content_type or "application/octet-stream"

        upload_url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": INPUT_BUCKET,
                "Key": input_key,
                "ContentType": content_type,
            },
            ExpiresIn=900,
        )

        upload_items.append(
            {
                "imageId": image_id,
                "filename": filename,
                "inputKey": input_key,
                "uploadUrl": upload_url,
                "method": "PUT",
                "headers": {"Content-Type": content_type},
            }
        )

        database_items.append(
            {
                "batchId": batch_id,
                "itemId": f"IMAGE#{image_id}",
                "imageId": image_id,
                "originalFilename": filename,
                "contentType": content_type,
                "inputKey": input_key,
                "status": "AWAITING_UPLOAD",
                "createdAt": created_at,
                "updatedAt": created_at,
                "expiresAt": expires_at,
            }
        )

    batch_record = {
        "batchId": batch_id,
        "itemId": "BATCH",
        "status": "AWAITING_UPLOAD",
        "totalImages": len(database_items),
        "operations": operation_data,
        "duplicateStatus": "NOT_STARTED",
        "duplicateReport": {"exact_duplicates": [], "similar_images": []},
        "createdAt": created_at,
        "updatedAt": created_at,
        "expiresAt": expires_at,
    }

    with table.batch_writer() as writer:
        writer.put_item(Item=batch_record)

        for item in database_items:
            writer.put_item(Item=item)

    return {
        "batchId": batch_id,
        "status": "AWAITING_UPLOAD",
        "expiresIn": 900,
        "uploads": upload_items,
        "operations": operation_data,
    }


@app.post("/batches/{batch_id}/start")
def start_batch(batch_id: str):
    batch = get_batch_record(batch_id)

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    current_status = batch.get("status")

    if current_status not in ("AWAITING_UPLOAD", "QUEUE_FAILED"):
        return {
            "batchId": batch_id,
            "status": current_status,
            "message": "This batch has already been started.",
        }

    images = get_batch_images(batch_id)

    if not images:
        raise HTTPException(status_code=400, detail="The batch contains no images.")

    missing_files = []

    for image in images:
        try:
            s3.head_object(Bucket=INPUT_BUCKET, Key=image["inputKey"])

        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")

            if error_code in ("404", "NoSuchKey", "NotFound"):
                missing_files.append(image["originalFilename"])
            else:
                raise HTTPException(
                    status_code=500,
                    detail=("Could not verify uploaded images: " f"{error}"),
                )

    if missing_files:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Some images have not been uploaded.",
                "missingFiles": missing_files,
            },
        )

    operations = batch.get("operations", {})
    output_format = operations.get("output_format", "WEBP").upper()

    output_extension = OUTPUT_EXTENSIONS[output_format]

    table.update_item(
        Key={"batchId": batch_id, "itemId": "BATCH"},
        UpdateExpression=(
            "SET #status = :status, "
            "updatedAt = :updated_at, "
            "duplicateStatus = :duplicate_status"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "QUEUING",
            ":updated_at": current_timestamp(),
            ":duplicate_status": "QUEUED",
        },
    )

    try:
        for image in images:
            output_key = (
                f"{batch_id}/processed/" f"{image['imageId']}{output_extension}"
            )

            message = {
                "jobType": "PROCESS_IMAGE",
                "batchId": batch_id,
                "imageId": image["imageId"],
                "inputBucket": INPUT_BUCKET,
                "inputKey": image["inputKey"],
                "outputKey": output_key,
                "originalFilename": (image["originalFilename"]),
                "operations": operations,
            }

            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps(message, default=json_default),
            )

            table.update_item(
                Key={"batchId": batch_id, "itemId": image["itemId"]},
                UpdateExpression=(
                    "SET #status = :status, "
                    "outputKey = :output_key, "
                    "updatedAt = :updated_at"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": "QUEUED",
                    ":output_key": output_key,
                    ":updated_at": current_timestamp(),
                },
            )

        duplicate_message = {
            "jobType": "DETECT_DUPLICATES",
            "batchId": batch_id,
            "inputBucket": INPUT_BUCKET,
            "threshold": int(operations.get("duplicate_threshold", 5)),
            "images": [
                {
                    "imageId": image["imageId"],
                    "originalFilename": (image["originalFilename"]),
                    "inputKey": image["inputKey"],
                }
                for image in images
            ],
        }

        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(duplicate_message, default=json_default),
        )

        table.update_item(
            Key={"batchId": batch_id, "itemId": "BATCH"},
            UpdateExpression=("SET #status = :status, " "updatedAt = :updated_at"),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "PROCESSING",
                ":updated_at": current_timestamp(),
            },
        )

    except Exception as error:
        table.update_item(
            Key={"batchId": batch_id, "itemId": "BATCH"},
            UpdateExpression=(
                "SET #status = :status, "
                "updatedAt = :updated_at, "
                "queueError = :queue_error"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "QUEUE_FAILED",
                ":updated_at": current_timestamp(),
                ":queue_error": str(error)[:1000],
            },
        )

        raise HTTPException(
            status_code=500, detail=f"Could not queue the batch: {error}"
        )

    return {
        "batchId": batch_id,
        "status": "PROCESSING",
        "queuedImages": len(images),
        "duplicateDetection": "QUEUED",
    }


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str):
    batch = get_batch_record(batch_id)

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    images = get_batch_images(batch_id)
    calculated_status = calculate_batch_status(images)

    if batch.get("status") != calculated_status and batch.get("status") not in (
        "AWAITING_UPLOAD",
        "QUEUE_FAILED",
    ):
        table.update_item(
            Key={"batchId": batch_id, "itemId": "BATCH"},
            UpdateExpression=("SET #status = :status, " "updatedAt = :updated_at"),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": calculated_status,
                ":updated_at": current_timestamp(),
            },
        )

    image_results = []

    for image in images:
        result = {
            "imageId": image["imageId"],
            "filename": image["originalFilename"],
            "status": image.get("status"),
            "inputKey": image.get("inputKey"),
            "outputKey": image.get("outputKey"),
            "outputFormat": image.get("outputFormat"),
            "outputSize": image.get("outputSize"),
            "error": image.get("errorMessage"),
            "downloadUrl": None,
        }

        if image.get("status") == "COMPLETED" and image.get("outputKey"):
            result["downloadUrl"] = output_download_url(image["outputKey"])

        image_results.append(result)

    completed = sum(image.get("status") == "COMPLETED" for image in images)

    failed = sum(image.get("status") == "FAILED" for image in images)

    return {
        "batchId": batch_id,
        "status": calculated_status,
        "total": len(images),
        "completed": completed,
        "failed": failed,
        "remaining": len(images) - completed - failed,
        "operations": batch.get("operations", {}),
        "duplicateStatus": batch.get("duplicateStatus", "NOT_STARTED"),
        "duplicates": batch.get(
            "duplicateReport", {"exact_duplicates": [], "similar_images": []}
        ),
        "images": image_results,
        "createdAt": batch.get("createdAt"),
        "updatedAt": batch.get("updatedAt"),
    }


handler = Mangum(app, lifespan="off")
