import os
import time
from material_compression.resizelib import cleanupVTF
from utils.formatting import format_size, format_percentage

def resize_and_compress(folder, size, progress_callback=None):
    old_size = 0
    new_size = 0
    replace_count = 0
    start_time = time.time()

    # First pass: count total files
    total_files = 0
    if progress_callback:
        for path, subdirs, files in os.walk(folder):
            for name in files:
                if name.endswith(".vtf"):
                    total_files += 1
        processed = 0

    for path, subdirs, files in os.walk(folder):
        for name in files:
            if not name.endswith(".vtf"):
                continue

            old_size_temp = os.path.getsize(os.path.join(path, name))
            converted = cleanupVTF(os.path.join(path, name), size)
            if converted:
                replace_count += 1
                new_size += os.path.getsize(os.path.join(path, name))
                old_size += old_size_temp
            else:
                new_size += old_size_temp
                old_size += old_size_temp
            
            if progress_callback:
                processed += 1
                progress_callback(processed, total_files)

    print("="*60)
    print("Replaced", replace_count, "files.")
    if replace_count == 0:
        print("No files were replaced.")
    else:
        print("Clamped to", size, "resolution.")
        print("Reduced size by ", format_percentage(old_size - new_size, old_size))
        print("Reduced size by ", format_size(old_size - new_size))
    print("Time taken:", round(time.time() - start_time, 2), "seconds")
    print("="*60)
    return old_size - new_size, replace_count
