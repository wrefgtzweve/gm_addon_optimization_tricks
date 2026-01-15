import os
from resizelib import cleanupVTF
from utils.formatting import format_size, format_percentage

# Edit these variables
PATH_TO_FILE = r"garrysmod\addons\addon_name\materials\material_name.vtf"
CLAMP_SIZE = 512
# End of variables

old_size = 0
new_size = 0
replace_count = 0

if not os.path.exists(PATH_TO_FILE):
    print("File does not exist:", PATH_TO_FILE)
    exit()

name = os.path.basename(PATH_TO_FILE)

filetype = name.split(".")[-1]
if filetype == "vtf":
    old_size = os.path.getsize(PATH_TO_FILE)
    cleanupVTF(PATH_TO_FILE, CLAMP_SIZE)
    new_size = os.path.getsize(PATH_TO_FILE)

print("Clamped to", CLAMP_SIZE, "pixels.")
if replace_count == 0:
    print("No files were replaced.")
else:
    print("Reduced size by ", format_percentage(old_size - new_size, old_size))
    print("Reduced size by ", format_size(old_size - new_size))
