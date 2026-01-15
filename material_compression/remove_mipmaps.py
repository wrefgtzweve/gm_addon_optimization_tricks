import os
import time
from sourcepp import vtfpp
from utils.formatting import format_size, format_percentage

def remove_mipmaps(folder, progress_callback=None):
    """Remove mipmaps from all VTF files in the specified folder
    
    Args:
        folder: Path to the folder containing VTF files
        progress_callback: Optional callback(current, total) for progress updates
    """
    old_size = 0
    new_size = 0
    processed_count = 0
    success_count = 0
    start_time = time.time()
    
    print(f"Scanning for VTF files in: {folder}")
    
    # First, count total files for progress tracking
    vtf_files = []
    for root, dirs, files in os.walk(folder):
        for filename in files:
            if filename.endswith(".vtf"):
                vtf_files.append(os.path.join(root, filename))
    
    total_files = len(vtf_files)
    print(f"Found {total_files} VTF files")
    print("Removing mipmaps from VTF files...")
    
    for idx, file_path in enumerate(vtf_files, 1):
        # Update progress
        if progress_callback:
            progress_callback(idx, total_files)
        
        old_file_size = os.path.getsize(file_path)
        old_size += old_file_size
        
        vtf = vtfpp.VTF(file_path)
        old_mipcount = vtf.mip_count
        if old_mipcount <= 1:
            new_size += old_file_size
            processed_count += 1
            continue
        
        vtf.mip_count = 0
        vtf.bake_to_file(file_path)
        
        success_count += 1
        new_file_size = os.path.getsize(file_path)
        new_size += new_file_size
        saved_bytes = old_file_size - new_file_size
        saved_mb = saved_bytes / (1024 * 1024)
        print(f"✓ {file_path} - {old_mipcount} -> 0 (saved {saved_mb:.2f} MB)")
        
        processed_count += 1
    
    print("="*60)
    print(f"Files processed: {processed_count}")
    print(f"Files modified: {success_count}")
    print(f"Files skipped: {processed_count - success_count}")
    
    if success_count > 0:
        total_saved = old_size - new_size
        mb_saved = total_saved / (1024 * 1024)
        
        print(f"Total size reduction: {mb_saved:.2f} MB ({format_percentage(total_saved, old_size)})")
        print(f"Average reduction per file: {mb_saved/success_count:.2f} MB")
    else:
        print("No files were modified.")
    
    print(f"Time taken: {round(time.time() - start_time, 2)} seconds")
    print("="*60)
    
    return (old_size - new_size, success_count)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        remove_mipmaps(sys.argv[1])
    else:
        print("Usage: python remove_mipmaps.py <folder_path>")
