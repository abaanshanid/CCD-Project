import json
import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import boto3

from processor import process_image
from utilities.duplicate import (
    calculate_perceptual_hash,
    calculate_sha256
)


s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

INPUT_BUCKET = os.environ["INPUT_BUCKET"]
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
TABLE_NAME = os.environ["TABLE_NAME"]

table = dynamodb.Table(TABLE_NAME)


OUTPUT_EXTENSIONS = {
    "WEBP": ".webp",
    "PNG": ".png",
    "JPEG": ".jpg",
    "JPG": ".jpg"
}


def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def update_image_status(
    batch_id,
    image_id,
    status,
    **additional_values
):
    expression_names = {
        "#status": "status"
    }

    expression_values = {
        ":status": status,
        ":updated_at": current_timestamp()
    }

    update_parts = [
        "#status = :status",
        "updatedAt = :updated_at"
    ]

    for field_name, value in additional_values.items():
        placeholder = f":{field_name}"

        expression_values[placeholder] = value
        update_parts.append(
            f"{field_name} = {placeholder}"
        )

    table.update_item(
        Key={
            "batchId": batch_id,
            "itemId": f"IMAGE#{image_id}"
        },
        UpdateExpression=(
            "SET " + ", ".join(update_parts)
        ),
        ExpressionAttributeNames=expression_names,
        ExpressionAttributeValues=expression_values
    )


def update_duplicate_status(
    batch_id,
    status,
    report=None,
    error=None
):
    expression_names = {
        "#duplicate_status": "duplicateStatus"
    }

    expression_values = {
        ":duplicate_status": status,
        ":updated_at": current_timestamp()
    }

    update_parts = [
        "#duplicate_status = :duplicate_status",
        "updatedAt = :updated_at"
    ]

    if report is not None:
        expression_values[":report"] = report
        update_parts.append(
            "duplicateReport = :report"
        )

    if error is not None:
        expression_values[":error"] = error[:1000]
        update_parts.append(
            "duplicateError = :error"
        )

    table.update_item(
        Key={
            "batchId": batch_id,
            "itemId": "BATCH"
        },
        UpdateExpression=(
            "SET " + ", ".join(update_parts)
        ),
        ExpressionAttributeNames=expression_names,
        ExpressionAttributeValues=expression_values
    )


def process_image_job(message):
    batch_id = message["batchId"]
    image_id = message["imageId"]
    input_key = message["inputKey"]

    input_bucket = message.get(
        "inputBucket",
        INPUT_BUCKET
    )

    operations = message.get(
        "operations",
        {}
    )

    output_format = operations.get(
        "output_format",
        operations.get("format", "WEBP")
    ).upper()

    if output_format not in OUTPUT_EXTENSIONS:
        raise ValueError(
            f"Unsupported output format: {output_format}"
        )

    output_extension = OUTPUT_EXTENSIONS[
        output_format
    ]

    input_extension = Path(
        input_key
    ).suffix.lower()

    temporary_id = uuid4().hex

    local_input_path = Path(
        f"/tmp/{temporary_id}{input_extension}"
    )

    local_output_path = Path(
        f"/tmp/{temporary_id}{output_extension}"
    )

    output_key = message.get(
        "outputKey",
        f"{batch_id}/{image_id}{output_extension}"
    )

    update_image_status(
        batch_id=batch_id,
        image_id=image_id,
        status="PROCESSING",
        inputKey=input_key,
        originalFilename=message.get(
            "originalFilename",
            Path(input_key).name
        )
    )

    try:
        print(
            f"Downloading "
            f"s3://{input_bucket}/{input_key}"
        )

        s3.download_file(
            input_bucket,
            input_key,
            str(local_input_path)
        )

        process_image(
            input_path=local_input_path,
            output_path=local_output_path,
            resize=operations.get("resize"),
            rotate=operations.get("rotate"),
            flip=operations.get("flip"),
            crop=operations.get("crop"),
            remove_background=operations.get(
                "remove_background",
                operations.get(
                    "backgroundRemoval",
                    False
                )
            ),
            output_format=output_format,
            quality=int(
                operations.get("quality", 85)
            )
        )

        content_type = (
            mimetypes.guess_type(
                local_output_path.name
            )[0]
            or "application/octet-stream"
        )

        print(
            f"Uploading "
            f"s3://{OUTPUT_BUCKET}/{output_key}"
        )

        s3.upload_file(
            str(local_output_path),
            OUTPUT_BUCKET,
            output_key,
            ExtraArgs={
                "ContentType": content_type
            }
        )

        output_size = (
            local_output_path.stat().st_size
        )

        update_image_status(
            batch_id=batch_id,
            image_id=image_id,
            status="COMPLETED",
            outputKey=output_key,
            outputFormat=output_format,
            outputSize=output_size
        )

        return {
            "jobType": "PROCESS_IMAGE",
            "batchId": batch_id,
            "imageId": image_id,
            "status": "COMPLETED",
            "outputKey": output_key
        }

    except Exception as error:
        print(
            f"Processing failed for "
            f"{image_id}: {error}"
        )

        update_image_status(
            batch_id=batch_id,
            image_id=image_id,
            status="FAILED",
            errorMessage=str(error)[:1000]
        )

        # Raising the error causes SQS to retry.
        raise

    finally:
        local_input_path.unlink(
            missing_ok=True
        )

        local_output_path.unlink(
            missing_ok=True
        )


def process_duplicate_job(message):
    batch_id = message["batchId"]

    input_bucket = message.get(
        "inputBucket",
        INPUT_BUCKET
    )

    threshold = int(
        message.get("threshold", 5)
    )

    images = message.get("images", [])

    temporary_folder = Path(
        f"/tmp/duplicates-{uuid4().hex}"
    )

    temporary_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    update_duplicate_status(
        batch_id=batch_id,
        status="PROCESSING"
    )

    try:
        image_hashes = []

        for image in images:
            image_id = image["imageId"]
            input_key = image["inputKey"]

            extension = (
                Path(input_key).suffix.lower()
                or ".img"
            )

            local_path = temporary_folder / (
                f"{image_id}{extension}"
            )

            print(
                f"Downloading duplicate-check image "
                f"s3://{input_bucket}/{input_key}"
            )

            s3.download_file(
                input_bucket,
                input_key,
                str(local_path)
            )

            image_hashes.append({
                "imageId": image_id,
                "filename": image[
                    "originalFilename"
                ],
                "sha256": calculate_sha256(
                    local_path
                ),
                "phash": calculate_perceptual_hash(
                    local_path
                )
            })

        exact_duplicates = []
        similar_images = []
        seen_hashes = {}

        # Find byte-for-byte identical images.
        for image in image_hashes:
            file_hash = image["sha256"]

            if file_hash in seen_hashes:
                original = seen_hashes[file_hash]

                exact_duplicates.append({
                    "originalImageId": (
                        original["imageId"]
                    ),
                    "original": (
                        original["filename"]
                    ),
                    "duplicateImageId": (
                        image["imageId"]
                    ),
                    "duplicate": (
                        image["filename"]
                    ),
                    "sha256": file_hash
                })

            else:
                seen_hashes[file_hash] = image

        # Find visually similar images.
        for first_index in range(
            len(image_hashes)
        ):
            for second_index in range(
                first_index + 1,
                len(image_hashes)
            ):
                first = image_hashes[
                    first_index
                ]

                second = image_hashes[
                    second_index
                ]

                # Exact duplicates were already
                # reported above.
                if (
                    first["sha256"]
                    == second["sha256"]
                ):
                    continue

                distance = (
                    first["phash"]
                    - second["phash"]
                )

                if distance <= threshold:
                    similar_images.append({
                        "firstImageId": (
                            first["imageId"]
                        ),
                        "first": (
                            first["filename"]
                        ),
                        "secondImageId": (
                            second["imageId"]
                        ),
                        "second": (
                            second["filename"]
                        ),
                        "distance": int(distance)
                    })

        duplicate_report = {
            "exact_duplicates": (
                exact_duplicates
            ),
            "similar_images": similar_images
        }

        update_duplicate_status(
            batch_id=batch_id,
            status="COMPLETED",
            report=duplicate_report
        )

        print(
            f"Duplicate detection completed for "
            f"batch {batch_id}: "
            f"{len(exact_duplicates)} exact, "
            f"{len(similar_images)} similar"
        )

        return {
            "jobType": "DETECT_DUPLICATES",
            "batchId": batch_id,
            "status": "COMPLETED",
            "exactDuplicates": len(
                exact_duplicates
            ),
            "similarImages": len(
                similar_images
            )
        }

    except Exception as error:
        print(
            f"Duplicate detection failed for "
            f"batch {batch_id}: {error}"
        )

        update_duplicate_status(
            batch_id=batch_id,
            status="FAILED",
            error=str(error)
        )

        # Raising the error causes SQS to retry.
        raise

    finally:
        shutil.rmtree(
            temporary_folder,
            ignore_errors=True
        )


def process_sqs_record(record):
    message = json.loads(record["body"])

    job_type = message.get(
        "jobType",
        "PROCESS_IMAGE"
    )

    if job_type == "PROCESS_IMAGE":
        return process_image_job(message)

    if job_type == "DETECT_DUPLICATES":
        return process_duplicate_job(message)

    raise ValueError(
        f"Unsupported job type: {job_type}"
    )


def handler(event, context):
    results = []

    for record in event.get("Records", []):
        results.append(
            process_sqs_record(record)
        )

    return {
        "processed": len(results),
        "results": results
    }