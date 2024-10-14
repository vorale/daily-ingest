import whisper
import ffmpeg
import os
import argparse
import ssl
from pathlib import Path
import subprocess
import json

def convert_media_to_wav(input_file, output_file):
    stream = ffmpeg.input(input_file)
    stream = ffmpeg.output(stream, output_file, acodec='pcm_s16le', ar='16000')
    ffmpeg.run(stream)

def extract_screenshots(input_path):
    probe = ffmpeg.probe(input_path)
    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    
    if video_stream is None:
        print(f"No video stream found in {input_path}")
        return

    # Try to get duration, use a default if not available
    duration = get_video_duration(input_path)
    if duration == 0:
        print(f"Warning: Couldn't determine video duration for {input_path}")
        # You might want to set a default duration or handle this case differently
        return

    # Extract screenshots
    for i in range(0, int(duration), 10):
        output_file = Path(input_path).parent / "screenshots" / f"{Path(input_path).stem}_screenshot_{i:04d}.jpg"
        subprocess.run([
            'ffmpeg', '-i', str(input_path), '-ss', str(i),
            '-vframes', '1', str(output_file)
        ], check=True)

def process_file(input_media):
    input_path = Path(input_media)
    output_wav = input_path.with_suffix('.wav')

    # Convert media to WAV
    convert_media_to_wav(str(input_path), str(output_wav))

    # # Extract screenshots if it's an MP4 file
    # if input_path.suffix.lower() == '.mp4':
    #     extract_screenshots(str(input_path))

    # Transcribe the audio
    ssl._create_default_https_context = ssl._create_unverified_context
    model = whisper.load_model("medium")
    result = model.transcribe(str(output_wav))

    # Write transcription to file
    output_txt = input_path.with_name(f"{input_path.stem}_transcription.txt")
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(result["text"])

    print(f"Transcription saved to: {output_txt}")
    print(f"WAV file saved to: {output_wav}")

    # The line that deletes the WAV file has been removed

def get_video_duration(input_path):
    try:
        # Run ffprobe command
        result = subprocess.run([
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(input_path)
        ], capture_output=True, text=True, check=True)
        
        # Parse the JSON output
        probe_data = json.loads(result.stdout)
        
        # Try to get duration from format
        duration = probe_data.get('format', {}).get('duration')
        if duration:
            return float(duration)
        
        # If not in format, try to find it in video stream
        for stream in probe_data.get('streams', []):
            if stream['codec_type'] == 'video':
                duration = stream.get('duration')
                if duration:
                    return float(duration)
        
        # If still not found, calculate from fps and nb_frames if available
        for stream in probe_data.get('streams', []):
            if stream['codec_type'] == 'video':
                nb_frames = stream.get('nb_frames')
                fps = eval(stream.get('avg_frame_rate', '0/1'))
                if nb_frames and fps:
                    return float(nb_frames) / fps
        
        print(f"Warning: Couldn't determine video duration for {input_path}")
        return 0
    
    except subprocess.CalledProcessError as e:
        print(f"Error running ffprobe: {e}")
        return 0
    except json.JSONDecodeError as e:
        print(f"Error parsing ffprobe output: {e}")
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 0

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Transcribe WebM and MP4 audio files to text.")
    parser.add_argument("--path", help="Path to the input media file or directory")
    parser.add_argument("--folder", help="Folder name under Downloads to process")
    args = parser.parse_args()

    if args.folder:
        downloads_path = Path.home() / "Downloads"
        input_path = downloads_path / args.folder
        if not input_path.is_dir():
            print(f"Error: {input_path} is not a valid directory.")
            return
    elif args.path:
        input_path = Path(args.path)
    else:
        print("Error: Either --path or --folder must be provided.")
        return

    if input_path.is_dir():
        # Get all WebM and MP4 files in the directory, sorted by size (large to small)
        media_files = sorted(
            [f for f in input_path.glob("*") if f.suffix.lower() in ('.webm', '.mp4')],
            key=lambda x: x.stat().st_size,
            reverse=True
        )
        for media_file in media_files:
            process_file(str(media_file))
    elif input_path.is_file() and input_path.suffix.lower() in ('.webm', '.mp4'):
        # Process a single WebM or MP4 file
        process_file(str(input_path))
    else:
        print(f"Error: {input_path} is not a valid WebM or MP4 file or directory containing such files.")

if __name__ == "__main__":
    main()
