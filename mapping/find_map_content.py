import shutil
import os
from srctools.bsp import BSP
from srctools.filesys import FileSystemChain, RawFileSystem
from srctools.packlist import PackList
from utils.vpk import get_vpk_files

def get_required_files_from_bsp(content_folder: str, bsp_path: str):
    """Return a list of all resource files needed for a given BSP map."""
    # 1. Open the BSP
    print(f"Loading BSP file: {bsp_path}")
    bsp = BSP(bsp_path)
    print("BSP loaded successfully.")
    
    # 2. Set up the filesystem
    fsys = FileSystemChain([])
    fsys.add_sys(RawFileSystem(content_folder))
    
    # 3. Create a PackList
    pack = PackList(fsys)
    
    # 4. Automatically gather all resources used by the BSP
    print("Gathering resources from BSP...")
    pack.pack_from_bsp(bsp)
    print("Resources gathered.")

    # 5. Evaluate dependencies (textures used by models, etc.), would need a VPK filesystem to do this properly
    # print("Evaluating dependencies...")
    # pack.eval_dependencies()
    # print("Dependencies evaluated.")
    
    # 5. Return all filenames
    return list(pack.filenames())

def find_map_content(all_content_folder: str, gamefolder:str, new_content_folder: str, map_file: str):
    """
    Find and copy all content used by a Source engine map file.
    
    Args:
        all_content_folder: Path to folder containing all content (materials, models, sounds, etc.)
        new_content_folder: Path to folder where found content should be copied
        map_file: Path to the .bsp map file to analyze
    """
    print(f"Finding content for map: {map_file}")
    print("="*60)
    
    if not os.path.exists(map_file):
        print(f"Error: Map file does not exist: {map_file}")
        return
    
    if not map_file.lower().endswith('.bsp'):
        print(f"Error: File is not a BSP file: {map_file}")
        return
    
    if not os.path.exists(all_content_folder):
        print(f"Error: Source content folder does not exist: {all_content_folder}")
        return
        
    print("Analyzing map file for used content...")
    required_files = get_required_files_from_bsp(all_content_folder, map_file)
    print(f"Total files needed: {len(required_files)}")
    
    # Get all files from VPK archives in the game folder
    vpk_files = get_vpk_files(gamefolder)

    # Copy the required files to the new content folder
    total_size = 0
    copied_count = 0
    map_base = os.path.splitext(os.path.basename(map_file))[0]
    for file_rel_path in required_files:
        # Normalize the relative path to use correct separators
        norm_rel_path = os.path.normpath(file_rel_path)

        # Fix lightmapped materials "materials\nature\water_wasteland002c_-7431_10685_225.vmt" -> "materials\nature\water_wasteland002c.vmt"
        if "_-" in norm_rel_path:
            parts = norm_rel_path.split("_-", 1)
            if parts[1].endswith(".vmt"):
                norm_rel_path = parts[0] + ".vmt"
            if parts[1].endswith(".vtf"):
                norm_rel_path = parts[0] + ".vtf"

        # Fix decals path, files starting with /decals/ are always stored in materials/decals/
        if norm_rel_path.startswith(os.path.normpath("decals/")):
            norm_rel_path = os.path.normpath("materials/" + norm_rel_path)

        # Generalize: remove 'maps/<mapname>/' from any path segment
        maps_segment = os.path.normpath(f"maps/{map_base}/")
        if maps_segment in norm_rel_path:
            parts = norm_rel_path.split(maps_segment, 1)
            norm_rel_path = os.path.normpath(parts[0] + parts[1])

        if norm_rel_path in vpk_files:
            continue

        src_path = os.path.normpath(os.path.join(all_content_folder, norm_rel_path))
        dest_path = os.path.normpath(os.path.join(new_content_folder, norm_rel_path))

        if os.path.exists(src_path):
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(src_path, dest_path)
            total_size += os.path.getsize(dest_path)
            copied_count += 1
        else:
            print(f"Warning: Required file not found: {norm_rel_path}")
    
    print("="*60)
    print(f"Content copying complete. Total size: {total_size / (1024*1024):.2f} MB Total files copied: {copied_count}")
    print(f"Files copied to: {new_content_folder}")
    return total_size, copied_count

