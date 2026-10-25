def crop_image(image, ratio):
    ratios = {
        "1:1": (1, 1),
        "4:3": (4, 3),
        "16:9": (16, 9)
    }

    if ratio not in ratios:
        return image

    target_w, target_h = ratios[ratio]

    width, height = image.size

    current_ratio = width / height
    target_ratio = target_w / target_h

    if current_ratio > target_ratio:
        # Image is too wide
        new_width = int(height * target_ratio)

        left = (width - new_width) // 2

        box = (
            left,
            0,
            left + new_width,
            height
        )

    else:
        # Image is too tall
        new_height = int(width / target_ratio)

        top = (height - new_height) // 2

        box = (
            0,
            top,
            width,
            top + new_height
        )

    return image.crop(box)