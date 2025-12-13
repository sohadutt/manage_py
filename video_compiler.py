import os
import subprocess
import imageio_ffmpeg  # For getting FFMPEG_PATH
import sys
from moviepy.editor import VideoFileClip, concatenate_videoclips
from moviepy.config import change_settings
from tqdm import tqdm  # For progress bars

# --- Tell MoviePy and Subprocess where FFmpeg is ---
try:
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    change_settings({"FFMPEG_BINARY": FFMPEG_PATH})
except Exception:
    print("Could not find ffmpeg.exe from imageio_ffmpeg.")
    print("Please make sure 'pip install imageio-ffmpeg' is working.")
    sys.exit(1)
# ----------------------------------------------------

# =============== CONFIGURATION ===============
MAIN_FOLDER = r"C:\Users\pc\Desktop\fanimation_compile"
EXPORT_FOLDER = os.path.join(MAIN_FOLDER, "export")
TARGET_FPS = 60

# --- Video Quality Settings ---
# 'preset' controls encoding speed vs. compression.
# Options: 'ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'
VIDEO_PRESET = "medium"  # 'medium' is a good balance. Use 'faster' if it's too slow.
# 'crf' controls quality (Constant Rate Factor). Lower = better quality.
# 18 is visually lossless. 23 is a good default. 28 is lower quality.
VIDEO_CRF = 18
# ============================================

def ensure_dir(path):
    """Create folder if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)

def change_fps(input_path, output_path, task_name):
    """
    Change video FPS to the target rate using FFmpeg.
    This duplicates frames (from 30 to 60) without blending or artifacts.
    """
    print(f"✨ Converting {task_name} to {TARGET_FPS} FPS (Frame Duplication)...")
    
    command = [
        FFMPEG_PATH,
        "-y",         # Overwrite output
        "-i", input_path,
        # Use the simple 'fps' filter to duplicate frames to reach TARGET_FPS
        "-vf", f"fps={TARGET_FPS}",
        # ----------------------------
        "-c:v", "libx264",
        "-crf", str(VIDEO_CRF),
        "-preset", VIDEO_PRESET,
        "-an",        # Remove audio
        output_path
    ]

    stderr_log = []
    try:
        # Use Popen to run the process and read its output in real-time
        process = subprocess.Popen(command,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 text=True,
                                 encoding='utf-8',
                                 errors='replace')

        print("--- FFmpeg Output ---")
        # Read stderr line by line (FFmpeg prints progress here)
        while True:
            line = process.stderr.readline()
            if not line:
                break
            line_stripped = line.strip()
            print(line_stripped)  # Print FFmpeg's raw progress
            stderr_log.append(line_stripped)
        
        print("-----------------------")
        process.wait()  # Wait for the process to finish

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command,
                                                 stdout=process.stdout.read(),
                                                 stderr='\n'.join(stderr_log))
                                                 
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during FPS conversion of {input_path}: {e}")
        print("\n--- FFmpeg Error Log ---")
        print(e.stderr)  # Print the captured log on failure
        print("------------------------")
    except FileNotFoundError:
        print(f"❌ Error: FFMPEG_PATH not found at: {FFMPEG_PATH}")
        print("Please ensure imageio_ffmpeg is installed and working.")

def compile_folder(folder_path):
    """Compile and interpolate videos inside a folder."""
    clips = []
    video_files = []

    # Get only video files sorted by numeric name
    try:
        video_files = sorted(
            [f for f in os.listdir(folder_path) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))],
            key=lambda x: int(os.path.splitext(x)[0]) if os.path.splitext(x)[0].isdigit() else x
        )
    except Exception as e:
        print(f"❌ Error sorting files in {folder_path}: {e}")
        return

    if not video_files:
        print(f"⚠️ No videos found in {folder_path}")
        return

    print(f"Found {len(video_files)} video clips. Reading files...")
    
    # --- Read video files ---
    for v in tqdm(video_files, desc="Reading clips", unit="clip"):
        video_path = os.path.join(folder_path, v)
        try:
            clips.append(VideoFileClip(video_path))
        except Exception as e:
            print(f"❌ Error reading clip {video_path}: {e}. Skipping.")
            continue
            
    if not clips:
        print(f"⚠️ No valid clips could be read from {folder_path}")
        return

    # --- NEW: Resize clips to match the first clip's resolution ---
    print("Checking clip resolutions...")
    first_clip_size = clips[0].size
    resized_clips = [clips[0]]
    for i, clip in enumerate(clips[1:], 1):
        if clip.size != first_clip_size:
            print(f"⚠️ Resizing clip {video_files[i]} from {clip.size} to {first_clip_size}")
            resized_clips.append(clip.resize(newsize=first_clip_size))
        else:
            resized_clips.append(clip)
    # -----------------------------------------------------------------

    try:
        final_clip = concatenate_videoclips(resized_clips, method="compose")
    except Exception as e:
        print(f"❌ Error during concatenation: {e}. Skipping folder.")
        # Close all opened clips
        for clip in resized_clips:
            clip.close()
        return

    # Temporary and final output paths
    task_name = os.path.basename(folder_path)
    temp_output = os.path.join(folder_path, "temp_compiled.mp4")
    final_output = os.path.join(EXPORT_FOLDER, f"{task_name}.mp4")

    print(f"🎞️ Compiling {len(clips)} videos from {folder_path}...")
    try:
        # Write temp file with TQDM progress bar
        final_clip.write_videofile(temp_output,
                                  codec="libx264",
                                  audio_codec="aac",
                                  fps=30, # Compiles at 30 FPS
                                  preset=VIDEO_PRESET,
                                  logger='bar') # <-- Uses TQDM
    except Exception as e:
        print(f"❌ Error writing temp file: {e}")
        final_clip.close()
        for clip in resized_clips:
            clip.close()
        return
    
    # Close all clip file handles
    final_clip.close()
    for clip in resized_clips:
        clip.close()

    # Convert the 30 FPS temp file to 60 FPS
    change_fps(temp_output, final_output, task_name)
    
    try:
        os.remove(temp_output)
    except PermissionError:
        print(f"⚠️ Could not remove temp file (still in use): {temp_output}")

    print(f"✅ Saved: {final_output}\n")

def main():
    ensure_dir(EXPORT_FOLDER)

    # Get list of folders to process
    folders_to_process = []
    for subfolder in os.listdir(MAIN_FOLDER):
        folder_path = os.path.join(MAIN_FOLDER, subfolder)
        if os.path.isdir(folder_path) and subfolder.lower() != "export":
            folders_to_process.append(folder_path)

    print(f"Found {len(folders_to_process)} folders to process.")
    
    # Wrap the main loop in tqdm for an overall progress bar
    for folder_path in tqdm(folders_to_process, desc="Total Progress", unit="folder"):
        folder_name = os.path.basename(folder_path)
        print(f"\n--- Processing folder: {folder_name} ---")
        compile_folder(folder_path)
        print(f"--- Finished folder: {folder_name} ---")

if __name__ == "__main__":
    main()