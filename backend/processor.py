from PIL import Image

from utilities.resize import resize_image
from utilities.rotate import rotate_image
from utilities.flip import flip_image
from utilities.crop import crop_image
from utilities.save import save_image
from utilities.background import remove_image_background

def process_image(
    input_path,
    output_path,
    resize=None,
    rotate=None,
    flip=None,
    crop=None,
    remove_background=False,
    output_format="WEBP",
    quality=85
):

    image = Image.open(input_path)

    # Background removal
    if remove_background:
        image = remove_image_background(image)
    # Crop
    if crop:
        image = crop_image(image, crop)

    # Rotate
    if rotate:
        image = rotate_image(image, rotate)

    # Flip
    if flip:
        image = flip_image(image, flip)

    # Resize
    if resize:
        image = resize_image(
        image=image,
        width=resize["width"],
        height=resize["height"],
        maintain_aspect_ratio=resize.get(
            "maintain_aspect_ratio",
            True
        )
    )
    # Convert + compress + save
    save_image(
        image,
        output_path,
        output_format,
        quality
    )


if __name__ == "__main__":

    process_image(
        input_path="test_images/test.jpg",
        output_path="output/test.webp",

        resize={
            "width": 1280,
            "height": 720
        },

        rotate=90,
        flip="horizontal",
        crop="16:9",

        output_format="WEBP",
        quality=75
    )
    process_image(
    "test_images/test.jpg",
    "output/resized.webp",
    resize={
        "width": 800,
        "height": 720
    }
)