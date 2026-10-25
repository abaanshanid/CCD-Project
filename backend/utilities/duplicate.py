import hashlib
from pathlib import Path

import imagehash
from PIL import Image, ImageOps


SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_PHASH_THRESHOLD = 5


def is_supported_image(file_path):
    """Return True if the file has a supported image extension."""
    return (
        file_path.is_file()
        and file_path.suffix.lower() in SUPPORTED_FORMATS
    )


def calculate_sha256(file_path):
    """Calculate the exact SHA-256 hash of a file."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        while chunk := file.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()


def calculate_perceptual_hash(file_path):
    """Calculate a perceptual hash based on the image's appearance."""
    with Image.open(file_path) as image:
        # Correct images containing phone/camera orientation metadata
        image = ImageOps.exif_transpose(image)

        # Convert to RGB so different image modes are handled consistently
        image = image.convert("RGB")

        return imagehash.phash(image)


def get_image_files(folder):
    """Return all supported images inside a folder."""
    folder = Path(folder)

    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")

    if not folder.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    return sorted(
        file_path
        for file_path in folder.iterdir()
        if is_supported_image(file_path)
    )


def find_exact_duplicates(folder):
    """
    Find byte-for-byte identical images using SHA-256.

    Returns:
        [
            {
                "original": "cat.jpg",
                "duplicate": "cat-copy.jpg",
                "sha256": "..."
            }
        ]
    """
    seen_hashes = {}
    duplicates = []

    for file_path in get_image_files(folder):
        try:
            file_hash = calculate_sha256(file_path)

            if file_hash in seen_hashes:
                duplicates.append({
                    "original": seen_hashes[file_hash].name,
                    "duplicate": file_path.name,
                    "sha256": file_hash
                })
            else:
                seen_hashes[file_hash] = file_path

        except OSError as error:
            print(f"Could not read {file_path.name}: {error}")

    return duplicates


def find_similar_images(folder, threshold=DEFAULT_PHASH_THRESHOLD):
    """
    Find visually similar images using perceptual hashes.

    A smaller distance means the images are more similar:
        0     = visually identical according to pHash
        1–5   = usually very similar
        large = increasingly different

    The threshold can be adjusted after testing.
    """
    image_hashes = []
    similar_images = []
    files = get_image_files(folder)

    # Calculate each image's SHA-256 and perceptual hash once
    for file_path in files:
        try:
            image_hashes.append({
                "path": file_path,
                "sha256": calculate_sha256(file_path),
                "phash": calculate_perceptual_hash(file_path)
            })

        except (OSError, ValueError) as error:
            print(f"Could not process {file_path.name}: {error}")

    # Compare every unique pair
    for first_index in range(len(image_hashes)):
        for second_index in range(first_index + 1, len(image_hashes)):
            first = image_hashes[first_index]
            second = image_hashes[second_index]

            # Exact copies are already reported by SHA-256
            if first["sha256"] == second["sha256"]:
                continue

            distance = first["phash"] - second["phash"]

            if distance <= threshold:
                similar_images.append({
                    "first": first["path"].name,
                    "second": second["path"].name,
                    "distance": distance
                })

    return similar_images


def generate_duplicate_report(folder, threshold=DEFAULT_PHASH_THRESHOLD):
    """Run both exact and perceptual duplicate detection."""
    return {
        "exact_duplicates": find_exact_duplicates(folder),
        "similar_images": find_similar_images(folder, threshold)
    }


def print_duplicate_report(report):
    """Print the duplicate report in a readable format."""
    exact_duplicates = report["exact_duplicates"]
    similar_images = report["similar_images"]

    print("\nEXACT DUPLICATES")
    print("----------------")

    if not exact_duplicates:
        print("No exact duplicates found.")
    else:
        for item in exact_duplicates:
            print(
                f"{item['duplicate']} is an exact duplicate "
                f"of {item['original']}"
            )

    print("\nSIMILAR IMAGES")
    print("--------------")

    if not similar_images:
        print("No similar images found.")
    else:
        for item in similar_images:
            print(
                f"{item['first']} and {item['second']} "
                f"have a pHash distance of {item['distance']}"
            )


if __name__ == "__main__":
    # duplicate.py is inside backend/utilities, so this locates backend/input
    backend_folder = Path(__file__).resolve().parent.parent
    input_folder = backend_folder / "input"

    try:
        duplicate_report = generate_duplicate_report(
            folder=input_folder,
            threshold=5
        )

        print_duplicate_report(duplicate_report)

    except (FileNotFoundError, NotADirectoryError) as error:
        print(error)