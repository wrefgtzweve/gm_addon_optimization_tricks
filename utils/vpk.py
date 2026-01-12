import glob
from typing import List, Set
import sourcepp
import os

def get_vpk_files(gamefolder: str) -> Set[str]:
    """
    Get all file paths from VPK files in the game folder.

    Args:
        gamefolder: Path to the game folder containing VPK files

    Returns:
        Set of file paths found in all VPK files
    """
    print("Getting files from VPK archives...")

    vpk_files = {}
    vpk_count = 0

    # Find all VPK files in the game folder
    vpk_patterns = [
        os.path.join(gamefolder, "**", "*.vpk"),
        os.path.join(gamefolder, "*.vpk")
    ]

    found_vpks = []
    for pattern in vpk_patterns:
        found_vpks.extend(glob.glob(pattern, recursive=True))

    # Remove duplicates and sort
    found_vpks = sorted(list(set(found_vpks)))

    if not found_vpks:
        print("No VPK files found in", gamefolder)
        return vpk_files

    print(f"Found {len(found_vpks)} VPK file(s) to process:")

    # Process each VPK file
    for vpk_path in found_vpks:
        try:
            # Counter for this VPK
            file_count = 0

            # Callback function to collect file paths
            vpk = None
            collected_files = []
            def collect_files(path: str, entry) -> None:
                nonlocal file_count
                path = os.path.normpath(path)
                collected_files.append(path)
                file_count += 1

            # Open the VPK and iterate through all files
            vpk = sourcepp.vpkpp.VPK.open(vpk_path, collect_files)
            for file_path in collected_files:
                vpk_files[file_path] = vpk

            vpk_count += 1
            print(f"  Found {file_count} files in {os.path.basename(vpk_path)}")

        except Exception as e:
            print(f"  Error processing {os.path.basename(vpk_path)}: {e}")
            continue

    print("="*60)
    print(f"Processed {vpk_count} VPK file(s) successfully.")
    print(f"Total files found: {len(vpk_files)}")
    print("="*60)

    return vpk_files
