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

        old_size += os.path.getsize(filepath)
        sound = pydub.AudioSegment.from_wav(filepath)

        new_filepath = filepath.replace(".wav", ".mp3")
        sound.export(new_filepath, format="mp3")
        new_size += os.path.getsize(new_filepath)

        file_name = os.path.basename(filepath)
        replace_count += 1
        replaced_files[file_name] = file_name.replace(".wav", ".mp3")
        os.remove(filepath)

        print("Converted", filepath, "to mp3 successfully.")

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

