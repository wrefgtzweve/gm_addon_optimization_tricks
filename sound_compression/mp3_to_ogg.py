import pydub
import pydub.exceptions
import os
import re
from utils.formatting import format_size, format_percentage

# Requires ffmpeg to be installed and added to PATH
# https://github.com/jiaaro/pydub?tab=readme-ov-file#getting-ffmpeg-set-up

def mp3_to_ogg(folder):
    replaced_files = {}
    old_size = 0
    new_size = 0
    replace_count = 0

    for path, subdirs, files in os.walk(folder):
        for name in files:
            filepath = os.path.join(path, name)
            filetype = name.split(".")[-1]
            if filetype == "mp3":
                old_size += os.path.getsize(filepath)
                try:
                    sound = pydub.AudioSegment.from_mp3(filepath)
                except pydub.exceptions.CouldntDecodeError as e:
                    print(f"Skipping corrupted MP3 file: {filepath} - Error: {e}")
                    continue
                except Exception as e:
                    print(f"Skipping MP3 file due to unexpected error: {filepath} - Error: {e}")
                    continue

                new_filepath = filepath.replace(".mp3", ".ogg")
                sound.export(new_filepath, format="ogg")
                new_size += os.path.getsize(new_filepath)

                file_name = os.path.basename(filepath)
                replace_count += 1
                replaced_files[file_name] = file_name.replace(".mp3", ".ogg")
                os.remove(filepath)

                print("Converted", filepath, "to ogg successfully.")

    for path, subdirs, files in os.walk(folder):
        for name in files:
            filepath = os.path.join(path, name)
            filetype = name.split(".")[-1]
            if filetype == "lua" or filetype == "txt" or filetype == "json":
                with open(filepath, "r", encoding="utf-8") as f:
                    contents = f.read()
                
                replaced = False
                for old, new in replaced_files.items():
                    pattern = re.escape(old)
                    new_contents = re.sub(pattern, new, contents, flags=re.IGNORECASE)
                    if new_contents != contents:
                        replaced = True
                    contents = new_contents

                if not replaced:
                    continue

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(contents)
                print("Replaced", filepath, "successfully.")

    print("="*60)
    print("Replaced", replace_count, "files.")
    if replace_count == 0:
        print("No files were replaced.")
    else:
        print("Reduced size by ", format_percentage(old_size - new_size, old_size))
        print("Reduced size by ", format_size(old_size - new_size))
    print("="*60)
    return old_size - new_size, replace_count
