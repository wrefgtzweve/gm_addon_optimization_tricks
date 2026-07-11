import os
import re
import tempfile

import pydub
import pydub.exceptions
from wavinfo import WavInfoReader

from utils.formatting import format_percentage, format_size

# Requires ffmpeg to be installed and added to PATH.
# https://github.com/jiaaro/pydub?tab=readme-ov-file#getting-ffmpeg-set-up

CODE_EXTENSIONS = {".lua", ".txt", ".json"}
SOUND_EXTENSIONS = {".wav", ".mp3"}
SKIP_DIRECTORIES = {".git", "__pycache__", "node_modules", "venv"}


def _walk_files(folder):
    """Walk a content folder while ignoring generated/dependency directories."""
    scanned_directories = 0
    for path, directories, files in os.walk(folder):
        directories[:] = [directory for directory in directories if directory.lower() not in SKIP_DIRECTORIES]
        scanned_directories += 1
        if scanned_directories % 100 == 0:
            print(f"Scanning... visited {scanned_directories} directories.", flush=True)
        yield path, files


def _find_sound_files(folder):
    sound_files = []
    for path, files in _walk_files(folder):
        for name in files:
            if os.path.splitext(name)[1].lower() in SOUND_EXTENSIONS:
                sound_files.append(os.path.join(path, name))
    return sound_files


def _read_code_files(folder, extra_lua_folders=None):
    contents = []

    scan_roots = [folder]
    for extra_folder in extra_lua_folders or []:
        extra_lua = os.path.join(extra_folder, "lua")
        scan_roots.append(extra_lua if os.path.exists(extra_lua) else extra_folder)

    for scan_root in scan_roots:
        print(f"Scanning code references in {scan_root}...")
        scanned_files = 0
        for path, files in _walk_files(scan_root):
            for name in files:
                if os.path.splitext(name)[1].lower() not in CODE_EXTENSIONS:
                    continue

                filepath = os.path.join(path, name)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as code_file:
                        contents.append((filepath, code_file.read()))
                        scanned_files += 1
                except OSError as error:
                    print(f"Skipping code file {filepath}: {error}")
        print(f"Scanned {scanned_files} code files in {scan_root}.", flush=True)

        # Soundscripts normally live outside the lua directory in scripts/*.txt.
        if scan_root != folder and os.path.basename(scan_root).lower() == "lua":
            scripts_root = os.path.join(os.path.dirname(scan_root), "scripts")
            if os.path.exists(scripts_root):
                for path, files in _walk_files(scripts_root):
                    for name in files:
                        if os.path.splitext(name)[1].lower() != ".txt":
                            continue

                        filepath = os.path.join(path, name)
                        try:
                            with open(filepath, "r", encoding="utf-8", errors="replace") as code_file:
                                contents.append((filepath, code_file.read()))
                        except OSError as error:
                            print(f"Skipping code file {filepath}: {error}")
    print(f"Scanned {len(contents)} Lua/TXT/JSON files for sound references.", flush=True)
    return contents


def _is_referenced(filepath, folder, reference_blob):
    filename = os.path.basename(filepath).lower()
    relative_path = os.path.relpath(filepath, folder).replace(os.sep, "/").lower()

    return filename in reference_blob or relative_path in reference_blob


def _has_wav_markers(filepath):
    try:
        wav_info = WavInfoReader(filepath)
    except Exception as error:
        print(f"Skipping WAV metadata check for {filepath}: {error}")
        return True

    if wav_info.cues is not None and len(wav_info.cues.cues) > 0:
        print(f"Skipping {filepath}: contains cue points.")
        return True

    if wav_info.smpl is not None and len(wav_info.smpl.sample_loops) > 0:
        print(f"Skipping {filepath}: contains loop points.")
        return True

    return False


def _convert_sound(filepath, preserve_filename=False):
    extension = os.path.splitext(filepath)[1].lower()
    temporary_filepath = None
    try:
        if extension == ".wav":
            sound = pydub.AudioSegment.from_wav(filepath)
        else:
            sound = pydub.AudioSegment.from_mp3(filepath)

        old_size = os.path.getsize(filepath)
        if preserve_filename:
            temporary_file = tempfile.NamedTemporaryFile(
                suffix=".ogg",
                prefix="sound_conversion_",
                dir=os.path.dirname(filepath),
                delete=False,
            )
            temporary_filepath = temporary_file.name
            temporary_file.close()
            new_filepath = filepath
            export_filepath = temporary_filepath
        else:
            new_filepath = os.path.splitext(filepath)[0] + ".ogg"
            export_filepath = new_filepath

        sound.export(
            export_filepath,
            format="ogg",
            codec="libvorbis",
            parameters=["-q:a", "4"],
        )
        new_size = os.path.getsize(export_filepath)
        if preserve_filename:
            os.replace(export_filepath, filepath)
            temporary_filepath = None
        else:
            os.remove(filepath)
    except pydub.exceptions.CouldntDecodeError as error:
        print(f"Skipping unreadable sound {filepath}: {error}")
        return None
    except Exception as error:
        print(f"Failed to convert {filepath}: {error}")
        return None
    finally:
        if temporary_filepath:
            try:
                os.remove(temporary_filepath)
            except OSError:
                pass

    if preserve_filename:
        print(f"Converted {filepath} to OGG while keeping its filename.")
        return old_size, new_size, None, None

    print(f"Converted {filepath} to {new_filepath} successfully.")
    return old_size, new_size, os.path.basename(filepath), os.path.basename(new_filepath)


def _replace_sound_references(code_contents, replacements):
    for filepath, contents in code_contents:
        original_contents = contents
        for old_name, new_name in replacements.items():
            contents = re.sub(re.escape(old_name), new_name, contents, flags=re.IGNORECASE)

        if contents == original_contents:
            continue

        try:
            with open(filepath, "w", encoding="utf-8") as code_file:
                code_file.write(contents)
            print(f"Replaced sound references in {filepath} successfully.")
        except OSError as error:
            print(f"Failed to update sound references in {filepath}: {error}")


def sounds_to_ogg(folder, extra_lua_folders=None, preserve_filenames=False, progress_callback=None):
    """Convert referenced WAV and MP3 files to OGG and update code references.

    Only sounds whose filename or relative path occurs in a Lua, TXT, or JSON file
    are converted. ``extra_lua_folders`` can contain companion addon folders whose
    Lua and soundscript files should also be searched. WAV files containing cue or
    loop points are left untouched. Unreferenced sounds are reported but never
    modified. When ``preserve_filenames`` is true, the converted OGG data replaces
    each source file in place without changing its filename or code references.
    """
    if progress_callback:
        progress_callback(0, 0)
    print("Searching for WAV and MP3 files...", flush=True)
    sound_files = _find_sound_files(folder)
    print(f"Found {len(sound_files)} WAV/MP3 files. Building reference list...", flush=True)
    code_contents = _read_code_files(folder, extra_lua_folders)
    print("Finished scanning code references. Matching sounds...", flush=True)
    reference_blob = "\n".join(contents.replace("\\", "/").lower() for _, contents in code_contents)

    referenced_files = []
    unfound_files = []
    for filepath in sound_files:
        if _is_referenced(filepath, folder, reference_blob):
            referenced_files.append(filepath)
        else:
            unfound_files.append(filepath)

    print(f"Found {len(sound_files)} WAV/MP3 sound files.", flush=True)
    print(f"Found {len(referenced_files)} referenced sound files.")
    if unfound_files:
        print("Unreferenced sounds:")
        for filepath in unfound_files:
            print(f"  {filepath}")
    else:
        print("No unreferenced WAV/MP3 sounds found.")

    replacements = {}
    old_size = 0
    new_size = 0
    replace_count = 0
    processed = 0
    total = len(referenced_files)

    print("Starting audio conversion...", flush=True)
    for filepath in referenced_files:
        processed += 1
        if progress_callback:
            progress_callback(processed, total)

        if os.path.splitext(filepath)[1].lower() == ".wav" and _has_wav_markers(filepath):
            continue

        result = _convert_sound(filepath, preserve_filename=preserve_filenames)
        if result is None:
            continue

        converted_old_size, converted_new_size, old_name, new_name = result
        old_size += converted_old_size
        new_size += converted_new_size
        replace_count += 1
        if old_name and new_name:
            replacements[old_name.lower()] = new_name

    _replace_sound_references(code_contents, replacements)

    print("=" * 60)
    print(f"Converted {replace_count} referenced sound files.")
    if replace_count == 0:
        print("No sound files were converted.")
    else:
        print("Reduced size by ", format_percentage(old_size - new_size, old_size))
        print("Reduced size by ", format_size(old_size - new_size))
    print("=" * 60)

    return old_size - new_size, replace_count
