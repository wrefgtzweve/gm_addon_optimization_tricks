import os
import tempfile

import pydub
import pydub.exceptions

from sound_compression.sounds_to_ogg import (
    _detect_audio_format,
    _find_sound_files,
    _has_wav_markers,
)
from utils.formatting import format_percentage, format_size

# Requires ffmpeg to be installed and added to PATH.
# https://github.com/jiaaro/pydub?tab=readme-ov-file#getting-ffmpeg-set-up

# How to re-encode audio data so it matches the container its extension claims.
_EXTENSION_EXPORT_SETTINGS = {
    ".wav": {"format": "wav"},
    ".mp3": {"format": "mp3", "codec": "libmp3lame", "parameters": ["-q:a", "4"]},
}


def _convert_to_extension_format(filepath, audio_format):
    """Re-encode ``filepath`` so its contents match its extension, in place."""
    extension = os.path.splitext(filepath)[1].lower()
    export_settings = _EXTENSION_EXPORT_SETTINGS[extension]
    temporary_filepath = None
    try:
        # Do not infer the input format from the filename. The whole point of
        # this tool is that the extension lies about the actual audio format.
        sound = pydub.AudioSegment.from_file(filepath, format=audio_format)

        old_size = os.path.getsize(filepath)
        temporary_file = tempfile.NamedTemporaryFile(
            suffix=extension,
            prefix="sound_extension_fix_",
            dir=os.path.dirname(filepath),
            delete=False,
        )
        temporary_filepath = temporary_file.name
        temporary_file.close()

        sound.export(temporary_filepath, **export_settings)
        new_size = os.path.getsize(temporary_filepath)
        os.replace(temporary_filepath, filepath)
        temporary_filepath = None
    except pydub.exceptions.CouldntDecodeError:
        # FFmpeg includes its complete stderr output in this exception. Keep the
        # log readable while still indicating that the file itself was left alone.
        print(
            f"Skipping unreadable sound {filepath} "
            f"(detected as {audio_format or 'unknown'}; the audio data may be invalid or mislabeled)."
        )
        return None
    except Exception as error:
        error_summary = str(error).splitlines()[-1] if str(error).strip() else "unknown error"
        print(f"Failed to convert {filepath}: {error_summary}")
        return None
    finally:
        if temporary_filepath:
            try:
                os.remove(temporary_filepath)
            except OSError:
                pass

    print(f"Converted {filepath} from {audio_format} to {extension.lstrip('.')}.")
    return old_size, new_size


def fix_sound_extensions(folder, progress_callback=None):
    """Re-encode sounds whose contents don't match their file extension.

    This is the inverse of :func:`sounds_to_ogg` with ``preserve_filenames``:
    instead of turning everything into OGG data, every sound is turned into
    the format its extension claims. A ``blah.wav`` that secretly contains
    OGG data becomes a real WAV file. Filenames are never changed, so code
    references keep working and don't need to be scanned. WAV files
    containing cue or loop points are skipped, since re-encoding would drop
    those markers.
    """
    if progress_callback:
        progress_callback(0, 0)
    print("Searching for WAV and MP3 files...", flush=True)
    sound_files = _find_sound_files(folder)
    print(f"Found {len(sound_files)} WAV/MP3 sound files.", flush=True)

    mismatched_files = []
    for filepath in sound_files:
        audio_format = _detect_audio_format(filepath)
        extension = os.path.splitext(filepath)[1].lower()
        if audio_format is None:
            print(f"Skipping {filepath}: format could not be detected.")
            continue
        if audio_format == extension.lstrip("."):
            continue  # Contents already match the extension.
        mismatched_files.append((filepath, audio_format))

    if not mismatched_files:
        print("No sounds with mismatched extensions found.")
    else:
        print(f"Found {len(mismatched_files)} sounds whose contents don't match their extension.")

    old_size = 0
    new_size = 0
    convert_count = 0
    processed = 0
    total = len(mismatched_files)

    print("Starting audio conversion...", flush=True)
    for filepath, audio_format in mismatched_files:
        processed += 1
        if progress_callback:
            progress_callback(processed, total)

        if audio_format == "wav" and _has_wav_markers(filepath):
            continue

        result = _convert_to_extension_format(filepath, audio_format)
        if result is None:
            continue

        converted_old_size, converted_new_size = result
        old_size += converted_old_size
        new_size += converted_new_size
        convert_count += 1

    print("=" * 60)
    print(f"Converted {convert_count} sound files to match their extension.")
    if convert_count == 0:
        print("No sound files were converted.")
    else:
        size_difference = new_size - old_size
        if size_difference > 0:
            print("Increased size by ", format_percentage(size_difference, old_size))
            print("Increased size by ", format_size(size_difference))
        else:
            print("Reduced size by ", format_percentage(-size_difference, old_size))
            print("Reduced size by ", format_size(-size_difference))
    print("=" * 60)

    return old_size - new_size, convert_count
