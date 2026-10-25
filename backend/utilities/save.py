def save_image(image, output_path, output_format, quality=85):

    output_format = output_format.upper()

    # JPEG cannot store transparency
    if output_format in ("JPEG", "JPG"):
        if image.mode != "RGB":
            image = image.convert("RGB")

        output_format = "JPEG"

    image.save(
        output_path,
        format=output_format,
        quality=quality,
        optimize=True
    )