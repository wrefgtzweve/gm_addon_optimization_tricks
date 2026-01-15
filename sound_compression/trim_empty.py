import os
import time
from pydub import AudioSegment, silence
from utils.formatting import format_size, format_percentage


def trim_single_audio_file(input_file, silence_thresh=-55, min_silence_len=50, fade_duration=200):
    """
    Trim silence from the end of a single audio file (WAV, MP3, or OGG) and apply fade-out.

    Args:
        input_file (str): Path to input audio file (WAV, MP3, or OGG).
        silence_thresh (int): Silence threshold in dBFS. Default -55 dB.
        min_silence_len (int): Minimum length of silence (ms) to trim. Default 50 ms.
        fade_duration (int): Duration of fade-out effect in milliseconds. Default 200 ms.
    
    Returns:
        tuple: (success, message, bytes_saved)
    """
    try:
        # Get original file size
        original_size = os.path.getsize(input_file)
        
        # Determine file format and load audio file
        file_ext = os.path.splitext(input_file)[1].lower()
        if file_ext == '.wav':
            audio = AudioSegment.from_wav(input_file)
            export_format = "wav"
        elif file_ext == '.mp3':
            audio = AudioSegment.from_mp3(input_file)
            export_format = "mp3"
        elif file_ext == '.ogg':
            audio = AudioSegment.from_ogg(input_file)
            export_format = "ogg"
        else:
            return False, f"Unsupported file format: {file_ext}", 0
        original_duration = len(audio)

        # Detect non-silent chunks
        non_silence_ranges = silence.detect_nonsilent(audio, 
                                                      min_silence_len=min_silence_len, 
                                                      silence_thresh=silence_thresh)

        if non_silence_ranges:
            # Get the last non-silent segment (only trim from end)
            end_trim = non_silence_ranges[-1][1]
            
            # Check if any trimming is needed from the end
            end_silence = original_duration - end_trim
            if end_silence <= min_silence_len:
                return False, f"No significant silence to trim from end ({end_silence}ms)", 0
            
            # Only trim from the end, keep the start intact
            trimmed_audio = audio[0:end_trim]
            
            # Apply fade-out effect to make the ending smoother
            if len(trimmed_audio) > fade_duration:
                trimmed_audio = trimmed_audio.fade_out(fade_duration)
            else:
                # If audio is shorter than fade duration, fade the entire audio
                trimmed_audio = trimmed_audio.fade_out(len(trimmed_audio))
            
            new_duration = len(trimmed_audio)
            
            # Export result with original format (overwrite original)
            trimmed_audio.export(input_file, format=export_format)
            
            # Calculate savings
            new_size = os.path.getsize(input_file)
            bytes_saved = original_size - new_size
            time_saved = original_duration - new_duration
            
            return True, f"Trimmed {time_saved/1000:.1f}s of silence from end + fade-out", bytes_saved
        else:
            return False, "No non-silent audio detected", 0
            
    except Exception as e:
        return False, f"Error processing file: {str(e)}", 0

def trim_empty_audio(folder, silence_thresh=-55, min_silence_len=50, fade_duration=200, progress_callback=None):
    """
    Trim silence from the end of all audio files (WAV, MP3, OGG) in the specified folder and apply fade-out.
    
    Args:
        folder (str): Path to folder containing audio files.
        silence_thresh (int): Silence threshold in dBFS. Default -55 dB.
        min_silence_len (int): Minimum length of silence (ms) to trim. Default 50 ms.
        fade_duration (int): Duration of fade-out effect in milliseconds. Default 200 ms.
        progress_callback: Optional callback function for progress updates (current, total).
    """
    old_size = 0
    new_size = 0
    processed_count = 0
    success_count = 0
    start_time = time.time()
    
    print(f"Scanning for audio files in: {folder}")
    print("Trimming silence from end of audio files (WAV, MP3, OGG) with fade-out...")
    
    # First pass: collect all audio files
    audio_files = []
    if progress_callback:
        for root, dirs, files in os.walk(folder):
            for filename in files:
                file_ext = filename.lower()
                if file_ext.endswith(".wav") or file_ext.endswith(".mp3") or file_ext.endswith(".ogg"):
                    audio_files.append(os.path.join(root, filename))
        total_files = len(audio_files)
        current_file = 0
    
    # Process all audio files
    for root, dirs, files in os.walk(folder):
        for filename in files:
            file_ext = filename.lower()
            if not (file_ext.endswith(".wav") or file_ext.endswith(".mp3") or file_ext.endswith(".ogg")):
                continue
                
            file_path = os.path.join(root, filename)
            
            if progress_callback:
                current_file += 1
                progress_callback(current_file, total_files)
            
            try:
                # Get original file size
                old_file_size = os.path.getsize(file_path)
                old_size += old_file_size
                
                # Process the file
                success, message, bytes_saved = trim_single_audio_file(file_path, silence_thresh, min_silence_len, fade_duration)
                processed_count += 1
                
                if success:
                    success_count += 1
                    new_file_size = os.path.getsize(file_path)
                    new_size += new_file_size
                    saved_mb = bytes_saved / (1024 * 1024)
                    print(f"✓ {file_path} - {message} (saved {saved_mb:.2f} MB)")
                else:
                    new_size += old_file_size  # No change in size
                
            except Exception as e:
                print(f"✗ {file_path} - Error: {str(e)}")
                new_size += old_file_size  # No change in size
    
    # Print summary
    print("="*60)
    print(f"Files processed: {processed_count}")
    print(f"Files modified: {success_count}")
    print(f"Files skipped: {processed_count - success_count}")
    
    if success_count > 0:
        total_saved = old_size - new_size
        mb_saved = total_saved / (1024 * 1024)
        
        print(f"Total size reduction: {mb_saved:.2f} MB ({format_percentage(total_saved, old_size)})")
        print(f"Average reduction per file: {mb_saved/success_count:.2f} MB")
    else:
        print("No files were modified.")
    
    print(f"Time taken: {round(time.time() - start_time, 2)} seconds")
    print("="*60)
    return old_size - new_size, success_count
