from PIL import ImageOps


def flip_image(image, direction):
    if direction == "horizontal":
        return ImageOps.mirror(image)

    elif direction == "vertical":
        return ImageOps.flip(image)

    return image