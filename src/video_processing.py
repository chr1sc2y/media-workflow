import json
import os
import subprocess

from .core import FileContext

# ffmpeg
ffmpeg_bin = "ffmpeg -hide_banner -loglevel error"


def execute(cmd: str, ctx: FileContext = None) -> bool:
    print(f"🔄 Processing: {os.path.basename(ctx.original_file)}")
    result = os.system(cmd)
    
    # Check command execution result and output file
    if result == 0 and os.path.exists(ctx.temp_file):
        # Get file sizes
        original_size = os.path.getsize(ctx.original_file)
        compressed_size = os.path.getsize(ctx.temp_file)
        compression_ratio = (1 - compressed_size / original_size) * 100
        
        ctx.archive_original_file()
        # ctx.delete_original_file()
        ctx.rename_temp_file()
        
        print(f"✅ Success: {os.path.basename(ctx.original_file)}")
        print(f"   Size: {format_file_size(original_size)} -> {format_file_size(compressed_size)} (saved {compression_ratio:.1f}%)\n")
        return True
    else:
        print(f"❌ Failed: {os.path.basename(ctx.original_file)} (exit code: {result})")
        # Clean up failed temporary file
        if os.path.exists(ctx.temp_file):
            os.remove(ctx.temp_file)
        return False


def get_video_bitrate(file_path: str) -> int:
    """
    Get the bitrate of a video file in bps (bits per second).
    Returns 0 if unable to detect.
    """
    try:
        # Use ffprobe to get video information
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return 0
        
        data = json.loads(result.stdout)
        
        # Try to get bitrate from format first
        if "format" in data and "bit_rate" in data["format"]:
            return int(data["format"]["bit_rate"])
        
        # Try to get from video stream
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and "bit_rate" in stream:
                return int(stream["bit_rate"])
        
        return 0
        
    except Exception as e:
        return 0


def get_video_fps(file_path: str) -> float:
    """
    Get the frame rate of a video file.
    Returns 0 if unable to detect.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return 0
        
        data = json.loads(result.stdout)
        
        # Get fps from video stream
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                # Try r_frame_rate first (more accurate)
                if "r_frame_rate" in stream:
                    fps_str = stream["r_frame_rate"]
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        return float(num) / float(den)
                # Fallback to avg_frame_rate
                if "avg_frame_rate" in stream:
                    fps_str = stream["avg_frame_rate"]
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        return float(num) / float(den)
        
        return 0
        
    except Exception as e:
        return 0


def get_video_resolution(file_path: str) -> tuple:
    """
    Get the resolution of a video file.
    Returns (width, height) or (0, 0) if unable to detect.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return (0, 0)
        
        data = json.loads(result.stdout)
        
        # Get resolution from video stream
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                width = stream.get("width", 0)
                height = stream.get("height", 0)
                return (width, height)
        
        return (0, 0)
        
    except Exception as e:
        return (0, 0)


def format_file_size(bytes_size: int) -> str:
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}TB"


def print_video_info(resolution_str: str, fps: float, original_mbps: float, target_mbps: float, ratio: float) -> None:
    """
    Print video processing information in a formatted way.
    
    Args:
        resolution_str: Resolution string (e.g., "1920x1080")
        fps: Frame rate
        original_mbps: Original bitrate in Mbps
        target_mbps: Target bitrate in Mbps
        ratio: Compression ratio (0.5 = 50%, 0.33 = 33%, etc.)
    """
    print(f"📊 {resolution_str} | {fps:.0f}fps | Bitrate: {original_mbps:.1f}M -> {target_mbps:.1f}M ({ratio*100:.0f}%)")




# Option:
# -i {1}            # Input file: Specifies the source video file path
# -vf scale={2}     # Video filter: Adjusts the resolution of the video based on the specified scale {2} value
# -r {3}            # Frame rate: Specifies the frame rate of the output video
# -c:v hevc_videotoolbox  # Video codec: Specifies the use of Apple's hardware-accelerated H.265/HEVC encoder via VideoToolbox framework
# -tag:v hvc1       # Video tag: Sets the HEVC tag to "hvc1" which is required for compatibility with Apple devices (iPhone/Mac)
# -b:v {bitrate}    # Video bitrate: Sets the target bitrate (default: 8M for balance, recommend: 6M for 1080p, 15M for 4K)
# -c:a aac          # Audio codec: Specifies AAC audio codec for compatibility
# -b:a 128k         # Audio bitrate: Sets audio bitrate to 128 kbps
# -map_metadata 0   # Metadata: Copies the metadata from the input video (e.g., title, author) to the output file
# {4}               # Output file: Specifies the destination path for the encoded video
# -y                # Overwrite: Automatically overwrites the output file if it already exists without asking for confirmation
def compress_video(ctx: FileContext, scale, fps, bitrate=None) -> bool:
    # Parameter validation
    if not scale:
        print(f"❌ Invalid scale parameter for {ctx.original_file_name}")
        return False
    
    if not fps or not isinstance(fps, (int, float)) or fps <= 0:
        print(f"❌ Invalid fps parameter for {ctx.original_file_name}: {fps}")
        return False
    
    # Set default bitrate
    video_bitrate = bitrate if bitrate else "8M"
    
    # Build command with audio processing
    cmd = "{0} -i {1} -vf scale={2} -r {3} \
        -c:v hevc_videotoolbox -tag:v hvc1 -b:v {4} \
        -c:a aac -b:a 128k \
        -map_metadata 0 {5} -y".format(
        ffmpeg_bin, ctx.original_file_name, scale, fps, video_bitrate, ctx.temp_file_name
    )
    return execute(cmd, ctx)


def compress_drone_video(ctx: FileContext, scale="1920:1080", bitrate="15M", fps=None) -> bool:
    """
    Compress drone video to fixed resolution and bitrate.
    Optimized for DJI drone videos - compresses to 1080p with fixed bitrate.
    Original videos are archived for preservation.
    
    Args:
        scale: Target resolution (default: "1920:1080" for 1080p)
        bitrate: Target video bitrate (default: "15M" for high quality, use "10M" for smaller size)
        fps: Target frame rate (default: None to keep original fps)
    """
    # Check if file exists
    if not os.path.exists(ctx.original_file):
        print(f"⚠️  Skipping: File not found - {os.path.basename(ctx.original_file)}")
        return False
    
    try:
        # Get original video info
        width, height = get_video_resolution(ctx.original_file)
        original_fps = get_video_fps(ctx.original_file)
        original_bitrate_bps = get_video_bitrate(ctx.original_file)
        
        # Use original fps if not specified
        if fps is None:
            fps = original_fps if original_fps > 0 else 30
        
        # Format display strings
        original_resolution = f"{width}x{height}" if width > 0 else "Unknown"
        original_mbps = original_bitrate_bps / 1_000_000 if original_bitrate_bps > 0 else 0
        target_mbps = float(bitrate.rstrip('Mk')) if isinstance(bitrate, str) else bitrate
        
        # Print processing info
        print(f"📊 {original_resolution} → 1920x1080 | {original_fps:.0f}fps → {fps:.0f}fps | Bitrate: {original_mbps:.1f}M → {target_mbps}M")
        
        # Build command with audio processing
        cmd = "{0} -i {1} -vf scale={2} -r {3} \
            -c:v hevc_videotoolbox -tag:v hvc1 -b:v {4} \
            -c:a aac -b:a 128k \
            -map_metadata 0 {5} -y".format(
            ffmpeg_bin, ctx.original_file_name, scale, fps, bitrate, ctx.temp_file_name
        )
        return execute(cmd, ctx)
    except Exception as e:
        print(f"⚠️  Error processing {os.path.basename(ctx.original_file)}: {e}")
        return False


def compress_rate(ctx: FileContext, video_rate="8M", audio_rate="128k", reserved=None) -> bool:
    """Compress video using specified video and audio bitrates."""
    cmd = "{0} -i {1} -b:v {2} -b:a {3} {4}".format(
        ffmpeg_bin, ctx.original_file_name, video_rate, audio_rate, ctx.temp_file_name
    )
    return execute(cmd, ctx)


def convert_webm_to_mp4(ctx: FileContext, scale, reserved1=None, reserved2=None) -> bool:
    """Convert WebM video to MP4 format."""
    ctx.set_format("mp4")
    cmd = "{0} -i {1} -vf scale={2} -c:v libx264 -pix_fmt yuv420p -crf 18 {3} -y".format(
        ffmpeg_bin, ctx.original_file_name, scale, ctx.temp_file_name
    )
    result = os.system(cmd)
    
    if result == 0 and os.path.exists(ctx.temp_file):
        ctx.archive_original_file()
        ctx.rename_temp_file()
        print(f"✅ Success: {os.path.basename(ctx.original_file)}\n")
        return True
    else:
        print(f"❌ Failed to convert {os.path.basename(ctx.original_file)}")
        if os.path.exists(ctx.temp_file):
            os.remove(ctx.temp_file)
        return False
