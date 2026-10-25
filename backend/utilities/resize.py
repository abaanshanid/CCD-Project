from PIL import Image


def resize_image(
    image,
    width,
    height,
    maintain_aspect_ratio=True
):
    if width <= 0 or height <= 0:
        raise ValueError("Width and height must be greater than zero.")

    if maintain_aspect_ratio:
        # Work on a copy so the original image is not modified
        resized_image = image.copy()

        # Fits the image inside the requested dimensions
        resized_image.thumbnail(
            (width, height),
            Image.Resampling.LANCZOS
        )

        return resized_image

    # Force the exact dimensions, even if this stretches the image
    return image.resize(
        (width, height),
        Image.Resampling.LANCZOS
    )