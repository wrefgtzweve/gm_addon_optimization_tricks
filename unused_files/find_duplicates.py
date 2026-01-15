import os
import xxhash
from utils.formatting import format_size


def find_duplicates(folder: str, remove: bool = False, progress_callback=None):
    hash_map = {}
    
    # Single pass: collect all files (excluding .git)
    all_files = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != '.git']
        for filename in files:
            all_files.append(os.path.join(root, filename))
    
    total_files = len(all_files)
    quick_hash_map = {}
    
    for idx, file_path in enumerate(all_files):
        try:
            quick_hash = calculate_quick_hash(file_path)
            quick_hash_map.setdefault(quick_hash, []).append(file_path)
        except (OSError, IOError) as e:
            print(f"Error hashing {file_path}: {e}")
        
        if progress_callback:
            progress_callback(idx + 1, total_files)
    
    for quick_hash, file_paths in quick_hash_map.items():
        if len(file_paths) > 1:
            for file_path in file_paths:
                try:
                    file_hash = calculate_file_hash(file_path)
                    hash_map.setdefault(file_hash, []).append(file_path)
                except (OSError, IOError) as e:
                    print(f"Error hashing {file_path}: {e}")
    
    duplicate_size = 0
    duplicate_count = 0
    duplicates_found = False
    
    for file_hash, paths in hash_map.items():
        if len(paths) > 1:
            duplicates_found = True
            print(f"\nFound {len(paths)} duplicates:")
            for path in paths:
                try:
                    print(f"  {path} ({format_size(os.path.getsize(path))})")
                except (OSError, FileNotFoundError):
                    pass
            
            for path in paths[1:]:
                try:
                    duplicate_size += os.path.getsize(path)
                    duplicate_count += 1
                except (OSError, FileNotFoundError):
                    pass
    
    if not duplicates_found:
        print("No duplicate files found.")
    else:
        print(f"\nTotal duplicates: {duplicate_count} files, {format_size(duplicate_size)}")
        
        if remove:
            removed_count = 0
            for paths in hash_map.values():
                if len(paths) > 1:
                    for path in paths[1:]:
                        try:
                            os.remove(path)
                            removed_count += 1
                            print(f"Removed: {path}")
                        except Exception as e:
                            print(f"Error removing {path}: {e}")
            print(f"Removed {removed_count} duplicate files.")
    
    return duplicate_size, duplicate_count


def calculate_quick_hash(file_path: str) -> str:
    """Quick hash using file size and first/last 4KB of file."""
    file_size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        first_bytes = f.read(4096)
        if file_size > 4096:
            f.seek(file_size - 4096)
            last_bytes = f.read(4096)
        else:
            last_bytes = b""
    
    hasher = xxhash.xxh64()
    hasher.update(str(file_size).encode())
    hasher.update(first_bytes)
    hasher.update(last_bytes)
    return hasher.hexdigest()


def calculate_file_hash(file_path: str, chunk_size: int = 524288) -> str:
    """Full file hash using xxHash with 512KB chunks."""
    hasher = xxhash.xxh64()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()
