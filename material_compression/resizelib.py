from PIL import Image
from sourcepp import vtfpp

def resizeVTFImage(vtf: vtfpp.VTF, path: str, max_size: int = 1024, best_format: vtfpp.ImageFormat = vtfpp.ImageFormat.DXT1) -> bool:
    w = vtf.width
    h = vtf.height
    neww = w
    newh = h

    scale = 1
    if w > max_size or h > max_size:
        maxd = max(w, h)
        scale = max_size / maxd
        neww *= scale
        newh *= scale

    if scale != 1:
        neww_int = int(neww)
        newh_int = int(newh)
        vtf.set_size(neww_int, newh_int, vtfpp.ImageConversion.ResizeFilter.NICE)
        vtf.bake_to_file(path)
        print(f"✓ {path} - resized from {w}x{h} to {neww_int}x{newh_int}")
        return True
    return False


def cleanupVTF(path: str, max_size: int = 9999) -> bool:
    if not path.endswith(".vtf"):
        return False
    
    try:
        vtf = vtfpp.VTF(path)
    except Exception as e:
        print(f"✗ {path} - failed to load VTF: {e}")
        return False

    try:
        image_data = vtf.get_image_data_as_rgba8888(0)
        image = Image.frombytes("RGBA", (vtf.width, vtf.height), image_data)
    except Exception as e:
        print(f"✗ {path} - failed to extract image data: {e}")
        return False

    _, _, _, a = image.split()

    best_format = vtfpp.ImageFormat.DXT1
    if a.getextrema()[0] < 255:
        best_format = vtfpp.ImageFormat.DXT5

    format_changed = False
    if vtf.format != best_format:
        vtf.set_format(best_format)
        format_changed = True

    if vtf.frame_count > 1:
        print("Skipping resize for animated VTF:", path)
        if format_changed:
            vtf.bake_to_file(path)
            return True
        return False

    if vtf.width > max_size or vtf.height > max_size:
        return resizeVTFImage(vtf, path, max_size, best_format)

    if format_changed:
        vtf.bake_to_file(path)
        return True

    return False
