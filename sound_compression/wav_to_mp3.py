import pydub
import os
import re
from wavinfo import WavInfoReader
from utils.formatting import format_size, format_percentage

# Requires ffmpeg to be installed and added to PATH
# https://github.com/jiaaro/pydub?tab=readme-ov-file#getting-ffmpeg-set-up

def wav_to_mp3(folder, progress_callback=None):
    replaced_files = {}
    old_size = 0
    new_size = 0
    replace_count = 0

    # Single pass: collect all WAV files
    wav_files = []
    for path, subdirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(".wav"):
                wav_files.append(os.path.join(path, name))

    total_wavs = len(wav_files)

    # Process WAV files
    for idx, filepath in enumerate(wav_files):
        if progress_callback:
            progress_callback(idx + 1, total_wavs)
        
        wav_info = WavInfoReader(filepath)
        if wav_info.cues is not None and len(wav_info.cues.cues) > 0:
            print("File", filepath, "contains cues, skipping.")
            continue

        if wav_info.smpl is not None and len(wav_info.smpl.sample_loops) > 0:
            print("File", filepath, "contains loops, skipping.")
            continue


        try:
            # Capture size before conversion attempt
            file_size = os.path.getsize(filepath)
            sound = pydub.AudioSegment.from_wav(filepath)

            # Use splitext for safe extension replacement (handles uppercase .WAV)
            base, _ = os.path.splitext(filepath)
            new_filepath = base + ".mp3"
            sound.export(new_filepath, format="mp3")
            converted_size = os.path.getsize(new_filepath)

            # Only update totals after successful conversion
            old_size += file_size
            new_size += converted_size

            file_name = os.path.basename(filepath)
            file_base, _ = os.path.splitext(file_name)
            replace_count += 1
            replaced_files[file_name] = file_base + ".mp3"
            os.remove(filepath)

            print("Converted", filepath, "to mp3 successfully.")
        except Exception as e:
            print(f"Error converting {filepath}: {e}")

    # Optimized reference replacement: O(N+M) instead of O(N*M)
    if replaced_files:
        # Build lowercased lookup for case-insensitive matching
        lower_lookup = {k.lower(): v for k, v in replaced_files.items()}
        
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
                    lambda m: lower_lookup.get(m.group(0).lower(), m.group(0)),
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

