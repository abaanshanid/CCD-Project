_session = None


def get_background_session():
    global _session

    # Load rembg only when background removal is selected
    from rembg import new_session

    if _session is None:
        _session = new_session("u2net")

    return _session


def remove_image_background(image):
    from rembg import remove

    return remove(
        image.convert("RGBA"),
        session=get_background_session()
    )