import os
from PIL import Image
from sourcepp import vtfpp
from utils.formatting import format_size


def is_single_color(image):
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    r, g, b, a = image.split()
    alpha_colors = a.getcolors(maxcolors=image.width * image.height)
    if alpha_colors is None or len(alpha_colors) != 1:
        return False
    
    if alpha_colors[0][1] != 255:
        return False

    rgb_image = Image.new('RGB', image.size)
    rgb_image.paste(image, mask=image.split()[3])
    colors = rgb_image.getcolors(maxcolors=image.width * image.height)
    return colors is not None and len(colors) == 1


def resize_single_color_images(folder, progress_callback=None):
    total_size = 0
    total_resized = 0
    total_resized_files = 0

    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tga', '.vtf')

    image_files = []
    for path, subdirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(image_extensions):
                image_files.append(os.path.join(path, name))

    total_image_count = len(image_files)
    processed = 0

    for filepath in image_files:
        try:
            original_size = os.path.getsize(filepath)
            total_size += original_size

            if filepath.lower().endswith('.vtf'):
                try:
                    vtf = vtfpp.VTF(filepath)
                    image_data = vtf.get_image_data_as_rgba8888(0)
                    image = Image.frombytes("RGBA", (vtf.width, vtf.height), image_data)

                    if is_single_color(image):
                        original_width = vtf.width
                        original_height = vtf.height
                        if original_width == 8 and original_height == 8:
                            total_resized += original_size
                            continue

                        vtf.set_size(8, 8, vtfpp.ImageConversion.ResizeFilter.NICE)
                        vtf.bake_to_file(filepath)

                        new_size = os.path.getsize(filepath)
                        total_resized += new_size
                        total_resized_files += 1
                        print(f"Resized single-color VTF {filepath} from ({original_width}x{original_height}) to 4x4 saving {format_size(original_size - new_size)}")
                    else:
                        total_resized += original_size
                except Exception as e:
                    print(f"Error processing VTF {filepath}: {e}")
                    total_resized += original_size
            else:
                image = Image.open(filepath)

                if is_single_color(image) and (image.width != 4 or image.height != 4):
                    image = image.resize((4, 4), resample=Image.Resampling.NEAREST)

                    if filepath.lower().endswith(('.png', '.bmp')):
                        image.save(filepath)
                    else:
                        image.save(filepath, quality=95)

                    new_size = os.path.getsize(filepath)
                    total_resized += new_size
                    total_resized_files += 1
                    print(f"Resized single-color image {filepath} to 4x4")
                else:
                    total_resized += original_size

        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            total_resized += original_size

        if progress_callback:
            processed += 1
            progress_callback(processed, total_image_count)

    if total_resized_files > 0:
        total_saved_mb = round((total_size - total_resized) / 1000000, 2)
        print("=" * 60)
        print(f"Resized {total_resized_files} single-color files, {total_saved_mb} mb saved")
        print("=" * 60)
    else:
        print("No single-color images found to resize.")

    return total_size - total_resized, total_resized_files
