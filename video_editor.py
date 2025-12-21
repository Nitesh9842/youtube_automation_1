import os
import logging
import subprocess
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
    logger.info("✅ FFmpeg-python loaded successfully")
except ImportError as e:
    logger.error(f"❌ FFmpeg-python not available: {e}")
    FFMPEG_AVAILABLE = False

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
    logger.info("✅ yt-dlp loaded successfully")
except ImportError as e:
    logger.error(f"❌ yt-dlp not available: {e}")
    YT_DLP_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    PIL_AVAILABLE = True
    logger.info("✅ PIL (Pillow) loaded successfully")
except ImportError as e:
    logger.error(f"❌ PIL not available: {e}")
    PIL_AVAILABLE = False

class VideoEditor:
    def __init__(self, temp_folder='temp_audio'):
        if not FFMPEG_AVAILABLE:
            raise ImportError("FFmpeg-python is required for video editing. Install with: pip install ffmpeg-python")
        
        self.temp_folder = temp_folder
        os.makedirs(temp_folder, exist_ok=True)
        logger.info(f"✅ VideoEditor initialized with temp folder: {temp_folder}")
        
        # Detect cloud environment
        self.is_cloud = self._detect_cloud_environment()
        
        # Verify FFmpeg binary is installed
        self.ffmpeg_installed = self._check_ffmpeg()
        if not self.ffmpeg_installed:
            error_msg = self._get_install_instructions()
            logger.error(error_msg)
            raise RuntimeError("FFmpeg binary not found. Please install FFmpeg to continue.")
    
    def _detect_cloud_environment(self):
        """Detect if running in a cloud/container environment"""
        cloud_indicators = [
            os.getenv('RENDER'),
            os.getenv('DYNO'),  # Heroku
            os.getenv('RAILWAY_ENVIRONMENT'),
            os.getenv('FLY_APP_NAME'),
            os.path.exists('/.dockerenv'),
            os.path.exists('/app'),  # Common in containers
            os.getenv('KUBERNETES_SERVICE_HOST'),
        ]
        is_cloud = any(cloud_indicators)
        if is_cloud:
            logger.info("🌐 Detected cloud/container environment")
        return is_cloud
    
    def _get_install_instructions(self):
        """Get FFmpeg installation instructions based on environment"""
        if self.is_cloud:
            return (
                "\n" + "="*60 + "\n"
                "❌ FFmpeg is NOT installed!\n"
                "="*60 + "\n"
                "For CLOUD DEPLOYMENT (Render, HuggingFace, Railway, etc.):\n\n"
                "1. Add a system package configuration file:\n\n"
                "   For Render (apt-based):\n"
                "   Create 'render.yaml':\n"
                "   services:\n"
                "     - type: web\n"
                "       buildCommand: apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt\n\n"
                "   OR create 'Aptfile' with content:\n"
                "   ffmpeg\n\n"
                "   For HuggingFace Spaces:\n"
                "   Add to 'packages.txt':\n"
                "   ffmpeg\n\n"
                "   For Docker:\n"
                "   Add to Dockerfile:\n"
                "   RUN apt-get update && apt-get install -y ffmpeg\n\n"
                "2. Redeploy your application\n\n"
                "="*60
            )
        else:
            return (
                "\n" + "="*60 + "\n"
                "❌ FFmpeg is NOT installed on your system!\n"
                "="*60 + "\n"
                "FFmpeg is required for video editing. Please install it:\n\n"
                "Option 1 - Using Chocolatey (Recommended for Windows):\n"
                "  1. Open PowerShell as Administrator\n"
                "  2. Run: choco install ffmpeg\n\n"
                "Option 2 - Manual Installation:\n"
                "  1. Download from: https://www.gyan.dev/ffmpeg/builds/\n"
                "  2. Extract the zip file\n"
                "  3. Add the 'bin' folder to your system PATH\n"
                "  4. Restart your terminal/IDE\n\n"
                "Option 3 - Using winget:\n"
                "  1. Run: winget install ffmpeg\n\n"
                "To verify installation, run: ffmpeg -version\n"
                "="*60
            )
    
    def _check_ffmpeg(self):
        """Check if FFmpeg is installed and accessible"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'], 
                capture_output=True, 
                check=True,
                timeout=5
            )
            logger.info("✅ FFmpeg binary found and working")
            return True
        except FileNotFoundError:
            logger.error("❌ FFmpeg binary not found in PATH")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ FFmpeg found but returned error: {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("❌ FFmpeg check timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error checking FFmpeg: {e}")
            return False
    
    def get_video_duration(self, video_path):
        """Get video duration using ffprobe"""
        try:
            probe = ffmpeg.probe(video_path)
            duration = float(probe['streams'][0]['duration'])
            return duration
        except Exception as e:
            logger.error(f"Error getting video duration: {e}")
            return 10.0  # Default fallback
    
    def download_youtube_audio(self, youtube_url):
        """Download audio from YouTube video"""
        if not YT_DLP_AVAILABLE:
            raise ImportError("yt-dlp is required. Install with: pip install yt-dlp")
        
        try:
            audio_path = os.path.join(self.temp_folder, 'background_music.m4a')
            
            # Remove old file if exists
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(self.temp_folder, 'background_music.%(ext)s'),
                'quiet': True,
                'no_warnings': True
            }
            
            logger.info(f"📥 Downloading audio from: {youtube_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
                info = ydl.extract_info(youtube_url, download=True)
                ext = info.get('ext', 'm4a')
                actual_path = os.path.join(self.temp_folder, f'background_music.{ext}')
            
            if os.path.exists(actual_path):
                logger.info(f"✅ Downloaded audio from YouTube: {actual_path}")
                return actual_path
            else:
                raise Exception("Audio file was not created")
            
        except Exception as e:
            logger.error(f"❌ Failed to download YouTube audio: {str(e)}")
            raise Exception(f"Failed to download music: {str(e)}")
    
    def create_text_overlay_image(self, text, video_width, video_height, position='top', fontsize=50):
        """Create a transparent PNG with text overlay using PIL"""
        if not PIL_AVAILABLE:
            raise ImportError("PIL (Pillow) is required. Install with: pip install Pillow")
        
        try:
            # Create transparent image
            img = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Load font
            try:
                font = ImageFont.truetype("arial.ttf", fontsize)
            except:
                try:
                    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", fontsize)
                except:
                    font = ImageFont.load_default()
            
            # Get text size
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Calculate position
            if position == 'top':
                x = (video_width - text_width) // 2
                y = 50
            elif position == 'bottom':
                x = (video_width - text_width) // 2
                y = video_height - text_height - 50
            elif position == 'center':
                x = (video_width - text_width) // 2
                y = (video_height - text_height) // 2
            else:
                x = (video_width - text_width) // 2
                y = 50
            
            # Draw text with outline
            stroke_width = 3
            for adj_x in range(-stroke_width, stroke_width + 1):
                for adj_y in range(-stroke_width, stroke_width + 1):
                    draw.text((x + adj_x, y + adj_y), text, font=font, fill=(0, 0, 0, 255))
            
            # Draw main text
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
            
            # Save to temp file
            temp_text_path = os.path.join(self.temp_folder, 'text_overlay.png')
            img.save(temp_text_path, 'PNG')
            
            return temp_text_path
            
        except Exception as e:
            logger.error(f"Failed to create text overlay: {str(e)}")
            return None
    
    def edit_video(self, video_path, output_path, music_url=None, music_volume=0.3,
                   text_overlays=None):
        """
        Complete video editing using FFmpeg
        
        Args:
            video_path: Path to input video
            output_path: Path for output video
            music_url: YouTube URL OR local file path for background music
            music_volume: Volume of background music (0.0 to 1.0)
            text_overlays: List of dict with keys: text, position, duration
        """
        if not self.ffmpeg_installed:
            raise RuntimeError(
                "FFmpeg is not installed. Please install FFmpeg first.\n"
                "See installation instructions above."
            )
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if os.path.isdir(output_path):
            video_filename = os.path.basename(video_path)
            output_path = os.path.join(output_path, os.path.splitext(video_filename)[0] + "_edited.mp4")
            logger.info(f"Output is a directory, saving to: {output_path}")
        
        try:
            logger.info(f"🎬 Starting video editing for: {video_path}")
            
            # Get video info
            probe = ffmpeg.probe(video_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            video_width = int(video_info['width'])
            video_height = int(video_info['height'])
            video_duration = float(probe['format']['duration'])
            
            logger.info(f"📊 Video info: {video_duration:.2f}s, {video_width}x{video_height}")
            
            # Start with input video
            video_input = ffmpeg.input(video_path)
            video_stream = video_input.video
            audio_stream = video_input.audio
            
            # Handle text overlays FIRST (before audio processing)
            if text_overlays and len(text_overlays) > 0:
                logger.info(f"📝 Adding {len(text_overlays)} text overlays")
                
                for i, overlay in enumerate(text_overlays):
                    text = overlay.get('text', 'Subscribe!')
                    position = overlay.get('position', 'top')
                    
                    logger.info(f"  Adding text {i+1}: '{text}' at {position}")
                    
                    # Create text overlay image
                    text_img_path = self.create_text_overlay_image(
                        text, video_width, video_height, position
                    )
                    
                    if text_img_path and os.path.exists(text_img_path):
                        logger.info(f"  Text overlay image created: {text_img_path}")
                        # Overlay text on video using proper overlay filter
                        text_input = ffmpeg.input(text_img_path, loop=1, t=video_duration)
                        video_stream = ffmpeg.filter([video_stream, text_input], 'overlay', x='0', y='0')
                    else:
                        logger.warning(f"  Failed to create text overlay image for: {text}")
            
            # Handle background music
            audio_path = None
            if music_url:
                if os.path.exists(music_url):
                    logger.info(f"🎵 Using local music file: {music_url}")
                    audio_path = music_url
                elif music_url.startswith('http'):
                    logger.info(f"🎵 Downloading music from YouTube: {music_url}")
                    audio_path = self.download_youtube_audio(music_url)
                else:
                    raise Exception(f"Invalid music source: {music_url}")
                
                if audio_path:
                    # Load background music
                    bg_music = ffmpeg.input(audio_path)
                    
                    # Adjust volume and trim to video length
                    bg_music = bg_music.filter('volume', volume=music_volume)
                    bg_music = bg_music.filter('atrim', duration=video_duration)
                    
                    # Replace original audio with background music
                    audio_stream = bg_music
            
            # Combine video and audio
            output = ffmpeg.output(
                video_stream, audio_stream, output_path,
                vcodec='libx264',
                acodec='aac',
                **{'b:a': '192k'},
                preset='medium',
                crf=23
            )
            
            # Run FFmpeg
            logger.info(f"💾 Writing edited video to: {output_path}")
            logger.info(f"⏳ This may take a few minutes... Please wait.")
            
            output = output.overwrite_output()
            ffmpeg.run(output, capture_stdout=True, capture_stderr=True, quiet=True)
            
            # Verify output
            if not os.path.exists(output_path):
                raise Exception(f"Output video file was not created: {output_path}")
            
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                raise Exception(f"Output video file is empty (0 bytes): {output_path}")
            
            file_size_mb = file_size / (1024 * 1024)
            logger.info(f"✅ Video editing completed: {output_path}")
            logger.info(f"📊 Output file size: {file_size_mb:.2f} MB")
            
            return output_path
            
        except ffmpeg.Error as e:
            stderr = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"❌ FFmpeg error: {stderr}")
            raise Exception(f"Video editing failed: {stderr}")
        except Exception as e:
            logger.error(f"❌ Video editing failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise Exception(f"Video editing failed: {str(e)}")
        finally:
            self.cleanup_temp_files()

    def cleanup_temp_files(self):
        """Clean up temporary files"""
        try:
            import time
            import gc
            
            gc.collect()
            time.sleep(0.5)
            
            if os.path.exists(self.temp_folder):
                for file in os.listdir(self.temp_folder):
                    file_path = os.path.join(self.temp_folder, file)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            logger.debug(f"🧹 Removed temp file: {file_path}")
                    except PermissionError:
                        logger.debug(f"⏭️ Skipping temp file (still in use): {file_path}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to remove {file_path}: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup temp files: {str(e)}")


def main():
    """Main function to run video editor with user input"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Edit videos with background music and text overlays')
    parser.add_argument('--video', type=str, help='Path to input video file')
    parser.add_argument('--music', type=str, help='YouTube URL for background music')
    parser.add_argument('--output', type=str, help='Path for output video file')
    parser.add_argument('--volume', type=float, default=0.3, help='Music volume (0.0 to 1.0, default: 0.3)')
    parser.add_argument('--text', type=str, help='Text overlay (optional)')
    parser.add_argument('--text-position', type=str, default='top', 
                       choices=['top', 'bottom', 'center', 'top-left', 'top-right'],
                       help='Text position (default: top)')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🎬 VIDEO EDITOR - Add Background Music & Text")
    print("="*60 + "\n")
    
    # Get video path
    if args.video:
        video_path = args.video
    else:
        video_path = input("📹 Enter path to your video file: ").strip().strip('"')
    
    # Validate video path
    if not os.path.exists(video_path):
        print(f"❌ Error: Video file not found: {video_path}")
        return
    
    # Get music URL
    if args.music:
        music_url = args.music
    else:
        music_url = input("🎵 Enter YouTube URL for background music (or press Enter to skip): ").strip()
        if not music_url:
            music_url = None
    
    # Get output path
    if args.output:
        output_path = args.output
    else:
        default_output = os.path.splitext(video_path)[0] + "_edited.mp4"
        output_path = input(f"💾 Enter output path (press Enter for '{default_output}'): ").strip().strip('"')
        if not output_path:
            output_path = default_output
    
    # Get volume
    music_volume = args.volume
    
    # Get text overlay
    text_overlays = None
    if args.text:
        text_overlays = [{
            'text': args.text,
            'position': args.text_position,
            'duration': None
        }]
    else:
        add_text = input("📝 Add text overlay? (y/n, press Enter to skip): ").strip().lower()
        if add_text == 'y':
            text = input("Enter text: ").strip()
            position = input("Position (top/bottom/center, default: top): ").strip() or 'top'
            text_overlays = [{
                'text': text,
                'position': position,
                'duration': None
            }]
    
    # Process video
    try:
        print("\n" + "="*60)
        print("🚀 Starting video editing...")
        print("="*60 + "\n")
        
        editor = VideoEditor()
        result = editor.edit_video(
            video_path=video_path,
            output_path=output_path,
            music_url=music_url,
            music_volume=music_volume,
            text_overlays=text_overlays
        )
        
        print("\n" + "="*60)
        print(f"✅ SUCCESS! Video saved to: {result}")
        
        # Verify and display file info
        if os.path.exists(result):
            file_size_mb = os.path.getsize(result) / (1024 * 1024)
            print(f"📁 File size: {file_size_mb:.2f} MB")
            print(f"📂 Open folder: {os.path.dirname(result)}")
        else:
            print("⚠️ Warning: Output file path shown but file not found!")
        
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
