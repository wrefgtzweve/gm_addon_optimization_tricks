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
        vtf.set_size(int(neww), int(newh), vtfpp.ImageConversion.ResizeFilter.NICE)
        vtf.bake_to_file(path)
        print(f"✓ {path} - resized from {w}x{h} to {int(neww)}x{int(newh)}")
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

    if vtf.frame_count > 1:
        if vtf.format in (vtfpp.ImageFormat.DXT1, vtfpp.ImageFormat.DXT5):
            print("Skipping resize for animated VTF:", path)
            return False
        try:
            image_data = vtf.get_image_data_as_rgba8888(0)
            image = Image.frombytes("RGBA", (vtf.width, vtf.height), image_data)
            _, _, _, a = image.split()
            best_format = vtfpp.ImageFormat.DXT5 if a.getextrema()[0] < 255 else vtfpp.ImageFormat.DXT1
            if vtf.format != best_format:
                vtf.set_format(best_format)
                vtf.bake_to_file(path)
                print("Skipping resize for animated VTF:", path)
                return True
        except Exception:
            pass
        print("Skipping resize for animated VTF:", path)
        return False

    needs_resize = vtf.width > max_size or vtf.height > max_size
    already_dxt = vtf.format in (vtfpp.ImageFormat.DXT1, vtfpp.ImageFormat.DXT5)
    
    if not needs_resize and already_dxt:
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

    if needs_resize:
        return resizeVTFImage(vtf, path, max_size, best_format)

    if format_changed:
        vtf.bake_to_file(path)
        return True

    return False
