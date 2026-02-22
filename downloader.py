import requests
import os
import uuid
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

def download_reel_with_audio(reel_url: str, output_folder: str = "downloads") -> str:
    """
    Download Instagram reel using RapidAPI
    
    Args:
        reel_url: Instagram reel URL
        output_folder: Folder to save downloaded video
        
    Returns:
        Path to downloaded video file
        
    Raises:
        Exception: If download fails
    """
    if not RAPIDAPI_KEY:
        raise Exception("RAPIDAPI_KEY not configured in .env file")
    
    logger.info(f"🚀 Fetching reel info from: {reel_url}")
    
    api_url = "https://instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com/convert"
    headers = {
        "x-rapidapi-host": "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }
    query = {"url": reel_url}
    
    try:
        response = requests.get(api_url, headers=headers, params=query, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        logger.info("✅ Response received successfully!")
        logger.info(f"📦 Response data keys: {list(data.keys())}")
        
        # Check for error in response
        if "error" in data or "message" in data:
            error_msg = data.get("error") or data.get("message", "Unknown API error")
            logger.error(f"❌ API returned error: {error_msg}")
            logger.error(f"Full response: {data}")
            raise Exception(f"API Error: {error_msg}")
        
        media_list = data.get("media", [])
        if not media_list:
            logger.error(f"❌ No 'media' field in response. Available fields: {list(data.keys())}")
            logger.error(f"Full response: {data}")
            raise Exception(f"No media found in API response. Response contains: {list(data.keys())}")
        
        video_url = media_list[0].get("url")
        if not video_url:
            logger.error(f"❌ No 'url' in media object. Media keys: {list(media_list[0].keys()) if media_list else 'empty'}")
            raise Exception("No video URL found in media response")
        
        logger.info(f"🎥 Download URL found: {video_url[:50]}...")
        
        # Create downloads folder if not exist
        os.makedirs(output_folder, exist_ok=True)
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        output_file = os.path.join(output_folder, f"reel_{unique_id}.mp4")
        
        logger.info("⬇️ Downloading video...")
        video_response = requests.get(video_url, stream=True, timeout=60)
        video_response.raise_for_status()
        
        with open(output_file, "wb") as f:
            for chunk in video_response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"✅ Video downloaded successfully: {output_file}")
        return output_file
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Request error: {str(e)}")
        raise Exception(f"Network error: {str(e)}")
    except KeyError as e:
        logger.error(f"❌ Invalid response format: {str(e)}")
        raise Exception(f"Invalid API response format: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Download error: {str(e)}")
        # Don't wrap the error message again if it's already descriptive
        raise

# For backward compatibility - can still run as standalone script
if __name__ == "__main__":
    url = input("Enter Instagram reel URL: ")
    try:
        video_path = download_reel_with_audio(url)
        print(f"✅ Video downloaded successfully! Saved as:\n{video_path}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
