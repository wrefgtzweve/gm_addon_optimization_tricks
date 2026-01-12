import os
import xxhash
from utils.vpk import get_vpk_files

def remove_game_files(folder, gamefolder, remove=True):
    """
    Remove files that exist in the game's VPK files from the addon folder.

    Args:
        folder: Path to the addon folder to clean
        gamefolder: Path to the game folder containing VPK files
        remove: If True, actually remove files. If False, just report what would be removed.
    """
    print("Removing game files...")

    # Get all files from VPK archives
    vpk_files = get_vpk_files(gamefolder)

    if not vpk_files:
        print("No files found in VPK archives. Nothing to remove.")
        return

    # Find files in the addon folder that match VPK files
    removed_count = 0
    removed_size = 0

    print(f"Scanning addon folder: {folder}")

    for root, dirs, files in os.walk(folder):
        for file in files:
            file_path = os.path.join(root, file)

            # Get relative path from the addon folder
            rel_path = os.path.relpath(file_path, folder)
            rel_path = os.path.normpath(rel_path)

            # Check if this file exists in any VPK
            if rel_path in vpk_files:
                vpk = vpk_files[rel_path]
                vpk_content = vpk.read_entry(rel_path)
                vpk_content_len = len(vpk_content)

                addon_file_size = os.path.getsize(file_path)
                if vpk_content_len != addon_file_size:
                    print(f"✗ File size mismatch {addon_file_size}/{vpk_content_len} for {rel_path}, skipping removal.")
                    continue

                # Comapre xxhashes of both files to ensure they are identical
                hasher = xxhash.xxh64()
                with open(file_path, "rb") as f:
                    while True:
                        data = f.read(65536)
                        if not data:
                            break
                        hasher.update(data)

                addon_file_hash = hasher.digest()
                vpk_file_hash = xxhash.xxh64(vpk_content).digest()
                if addon_file_hash != vpk_file_hash:
                    print(f"✗ File hash mismatch for {rel_path}, skipping removal.")
                    continue

                file_size = os.path.getsize(file_path)
                removed_size += file_size
                removed_count += 1

                if remove:
                    try:
                        os.remove(file_path)
                        print(f"✓ Removed: {rel_path}")
                    except Exception as e:
                        print(f"✗ Failed to remove {rel_path}: {e}")
                else:
                    print(f"✓ Would remove: {rel_path}")

    # check for empty directories and remove them
    for root, dirs, files in os.walk(folder, topdown=False):
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            if not os.listdir(dir_path):
                if remove:
                    try:
                        os.rmdir(dir_path)
                        print("Removed empty directory: %s" % os.path.relpath(dir_path, folder).replace('\\', '/'))
                    except Exception as e:
                        print(f"Failed to remove directory {dir_path}: {e}")
                else:
                    print("Would remove empty directory: %s" % os.path.relpath(dir_path, folder).replace('\\', '/'))

    print("="*60)
    if remove:
        print(f"Removed {removed_count} game files.")
    else:
        print(f"Would remove {removed_count} game files.")

    if removed_count == 0:
        print("No game files were found in the addon folder.")
    else:
        print(f"Freed up {round(removed_size / 1000000, 2)} MB of space")
    print("="*60)
