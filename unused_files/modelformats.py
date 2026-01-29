import os


def unused_model_formats(folder, remove=True, progress_callback=None):
    total_size = 0
    count = 0

    formats_to_remove = [
        ".dx80.vtx",
        ".xbox.vtx",
        ".sw.vtx",
        ".360.vtx"
    ]

    # Single pass: collect all matching files
    files_to_process = []
    for root, _, files in os.walk(folder):
        for file in files:
            for fmt in formats_to_remove:
                if file.endswith(fmt):
                    files_to_process.append(os.path.join(root, file))
                    break  # Don't add same file multiple times

    total_count = len(files_to_process)

    # Process collected files
    for idx, file_path in enumerate(files_to_process):
        total_size += os.path.getsize(file_path)
        if remove:
            os.remove(file_path)
            print("Removed", file_path)
        else:
            print("Found unused file:", file_path)
        count += 1
        
        if progress_callback:
            progress_callback(idx + 1, total_count)

    return total_size, count

