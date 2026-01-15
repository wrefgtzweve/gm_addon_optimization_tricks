import pydub
import os
import re
from wavinfo import WavInfoReader
from utils.formatting import format_size

# Requires ffmpeg to be installed and added to PATH
# https://github.com/jiaaro/pydub?tab=readme-ov-file#getting-ffmpeg-set-up

def wav_to_ogg(folder, progress_callback=None):
    replaced_files = {}
    old_size = 0
    new_size = 0
    replace_count = 0

    # First pass: count WAV files
    wav_files = []
    if progress_callback:
        for path, subdirs, files in os.walk(folder):
            for name in files:
                if name.split(".")[-1] == "wav":
                    wav_files.append(os.path.join(path, name))
        total_wavs = len(wav_files)
        processed = 0

    for path, subdirs, files in os.walk(folder):
        for name in files:
            filepath = os.path.join(path, name)
            filetype = name.split(".")[-1]
            if filetype == "wav":
                if progress_callback:
                    processed += 1
                    progress_callback(processed, total_wavs)
                
                wav_info = WavInfoReader(filepath)
                if wav_info.cues != None and len(wav_info.cues.cues) > 0:
                    print("File", filepath, "contains cues skipping.")
                    continue

                if wav_info.smpl != None and len(wav_info.smpl.sample_loops) > 0:
                    print("File", filepath, "contains loops skipping.")
                    continue

                old_size += os.path.getsize(filepath)
                sound = pydub.AudioSegment.from_wav(filepath)

                new_filepath = filepath.replace(".wav", ".ogg")
                sound.export(new_filepath, format="ogg")
                new_size += os.path.getsize(new_filepath)

                file_name = os.path.basename(filepath)
                replace_count += 1
                replaced_files[file_name] = file_name.replace(".wav", ".ogg")
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
        print("Reduced size by ", round((1 - new_size / old_size) * 100, 2), "%")
        print("Reduced size by ", format_size(old_size - new_size))
    print("="*60)
