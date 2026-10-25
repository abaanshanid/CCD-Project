from pathlib import Path

from processor import process_image
from utilities.duplicate import (
    generate_duplicate_report,
    print_duplicate_report
)


SUPPORTED_FORMATS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

OUTPUT_EXTENSIONS = {
    "WEBP": ".webp",
    "PNG": ".png",
    "JPEG": ".jpg",
    "JPG": ".jpg"
}


def get_unique_output_path(
    output_folder,
    filename,
    extension
):
    """
    Prevent output files from overwriting one another.

    Example:
        photo.jpg -> photo.webp
        photo.png -> photo_1.webp
    """
    output_path = output_folder / f"{filename}{extension}"
    counter = 1

    while output_path.exists():
        output_path = output_folder / (
            f"{filename}_{counter}{extension}"
        )
        counter += 1

    return output_path


def process_batch(
    input_folder,
    output_folder,
    resize=None,
    rotate=None,
    flip=None,
    crop=None,
    remove_background=False,
    output_format="WEBP",
    quality=85,
    duplicate_threshold=5
):
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    # Validate input folder
    if not input_folder.exists():
        raise FileNotFoundError(
            f"Input folder does not exist: {input_folder}"
        )

    if not input_folder.is_dir():
        raise NotADirectoryError(
            f"Input path is not a folder: {input_folder}"
        )

    # Create output folder if necessary
    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    output_format = output_format.upper()

    if output_format not in OUTPUT_EXTENSIONS:
        raise ValueError(
            "Unsupported output format. "
            "Use WEBP, PNG, JPEG or JPG."
        )

    # Warn when transparency would be lost
    if remove_background and output_format in ("JPEG", "JPG"):
        print(
            "Warning: JPEG does not support transparency. "
            "Use PNG or WEBP to preserve the removed background."
        )

    # Find supported images
    image_files = sorted(
        file_path
        for file_path in input_folder.iterdir()
        if (
            file_path.is_file()
            and file_path.suffix.lower() in SUPPORTED_FORMATS
        )
    )

    if not image_files:
        print("No supported images found in the input folder.")

        return {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "results": [],
            "duplicates": {
                "exact_duplicates": [],
                "similar_images": []
            }
        }

    # Detect duplicates for reporting only.
    # No images are skipped or deleted.
    print("CHECKING FOR DUPLICATES")
    print("-----------------------")

    duplicate_report = generate_duplicate_report(
        folder=input_folder,
        threshold=duplicate_threshold
    )

    print_duplicate_report(duplicate_report)

    completed = 0
    failed = 0
    results = []

    output_extension = OUTPUT_EXTENSIONS[output_format]

    print("\nBATCH PROCESSING")
    print("----------------")

    for input_path in image_files:
        output_path = get_unique_output_path(
            output_folder=output_folder,
            filename=input_path.stem,
            extension=output_extension
        )

        print(f"\nProcessing: {input_path.name}")

        try:
            process_image(
                input_path=input_path,
                output_path=output_path,
                resize=resize,
                rotate=rotate,
                flip=flip,
                crop=crop,
                remove_background=remove_background,
                output_format=output_format,
                quality=quality
            )

            completed += 1

            results.append({
                "input_file": input_path.name,
                "output_file": output_path.name,
                "status": "completed",
                "error": None
            })

            print(f"Completed: {input_path.name}")
            print(f"Output: {output_path.name}")

        except Exception as error:
            failed += 1

            results.append({
                "input_file": input_path.name,
                "output_file": None,
                "status": "failed",
                "error": str(error)
            })

            print(f"Failed: {input_path.name}")
            print(f"Reason: {error}")

    print("\nBATCH SUMMARY")
    print("-------------")
    print(f"Total images: {len(image_files)}")
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    print(
        "Exact duplicate pairs detected: "
        f"{len(duplicate_report['exact_duplicates'])}"
    )
    print(
        "Visually similar pairs detected: "
        f"{len(duplicate_report['similar_images'])}"
    )

    return {
        "total": len(image_files),
        "completed": completed,
        "failed": failed,
        "results": results,
        "duplicates": duplicate_report
    }


if __name__ == "__main__":
    backend_folder = Path(__file__).resolve().parent

    process_batch(
        input_folder=backend_folder / "input",
        output_folder=backend_folder / "output",

        resize={
            "width": 1280,
            "height": 720,
            "maintain_aspect_ratio": True
        },

        rotate=90,
        flip="horizontal",
        crop="16:9",

        # Change to False when background removal is not wanted
        remove_background=True,

        # PNG and WEBP support transparent backgrounds
        output_format="PNG",

        quality=75,
        duplicate_threshold=5
    )