import pydub
import pydub.exceptions
import os
import re
from utils.formatting import format_size, format_percentage

# Requires ffmpeg to be installed and added to PATH
# https://github.com/jiaaro/pydub?tab=readme-ov-file#getting-ffmpeg-set-up

def mp3_to_ogg(folder, progress_callback=None):
    replaced_files = {}
    old_size = 0
    new_size = 0
    replace_count = 0

    # Single pass: collect all MP3 files
    mp3_files = []
    for path, subdirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(".mp3"):
                mp3_files.append(os.path.join(path, name))

    total_mp3s = len(mp3_files)

    # Process MP3 files
    for idx, filepath in enumerate(mp3_files):
        if progress_callback:
            progress_callback(idx + 1, total_mp3s)
        
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

    # Optimized reference replacement: O(N+M) instead of O(N*M)
    if replaced_files:
        # Build combined regex pattern for all replacements
        pattern = re.compile(
            '|'.join(re.escape(old) for old in replaced_files.keys()),
            flags=re.IGNORECASE
        )
        
        # Collect text files in single pass
        text_files = []
        for path, subdirs, files in os.walk(folder):
            for name in files:
                if name.lower().endswith((".lua", ".txt", ".json")):
                    text_files.append(os.path.join(path, name))
        
        # Process each text file once with all replacements
        for filepath in text_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    contents = f.read()
                
                # Single regex pass replaces all matches
                new_contents = pattern.sub(
                    lambda m: replaced_files.get(m.group(0), replaced_files.get(m.group(0).lower(), m.group(0))),
                    contents
                )
                
                if new_contents != contents:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_contents)
                    print("Replaced", filepath, "successfully.")
            except Exception as e:
                print(f"Error processing {filepath}: {e}")

    print("="*60)
    print("Replaced", replace_count, "files.")
    if replace_count == 0:
        print("No files were replaced.")
    else:
        print("Reduced size by ", format_percentage(old_size - new_size, old_size))
        print("Reduced size by ", format_size(old_size - new_size))
    print("="*60)
    return old_size - new_size, replace_count

