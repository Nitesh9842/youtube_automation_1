import os
import json
from typing import List, Dict, Optional
import cv2
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image
import numpy as np
import base64
from io import BytesIO

# GROQ SDK
from groq import Groq

# Load ENV
load_dotenv()


class AIMetadataGenerator:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key not found!")

        self.client = Groq(api_key=self.api_key)
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"  # New vision-capable model
        self.text_model = "llama-3.3-70b-versatile"  # Text model

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def extract_video_frames(self, video_path: str, num_frames: int = 3) -> List[Image.Image]:
        """Extract key frames from video"""
        try:
            cap = cv2.VideoCapture(video_path)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frames = []

            for i in range(num_frames):
                frame_number = int((i + 1) * frame_count / (num_frames + 1))
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()

                if ret:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)
                    pil_image = pil_image.resize((512, 512), Image.Resampling.LANCZOS)
                    frames.append(pil_image)

            cap.release()
            return frames

        except Exception as e:
            print(f"Frame Error: {e}")
            return []

    def analyze_video_content(self, video_path: str) -> str:
        """Analyze extracted video frames with Groq Vision"""
        try:
            frames = self.extract_video_frames(video_path, 3)
            if not frames:
                return "Unable to analyze video content."

            combined = []

            for i, frame in enumerate(frames):
                base64_image = self._image_to_base64(frame)
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"""Analyze frame {i+1} deeply. Extract:
                                    - Visible text
                                    - Main subject
                                    - Action happening
                                    - Location/setting
                                    - Key objects
                                    Provide a detailed structured explanation."""
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=1024
                )

                combined.append(response.choices[0].message.content)

            final_resp = self.client.chat.completions.create(
                model=self.text_model,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Based on these frame analyses:
                        {' '.join(combined)}
                        
                        Create a single concise summary of the video."""
                    }
                ],
                max_tokens=512
            )

            return final_resp.choices[0].message.content.strip() if final_resp.choices[0].message.content else "Video analysis unavailable."

        except Exception as e:
            print(f"Analysis Error: {e}")
            return "Video analysis unavailable."

    def generate_title(self, video_analysis: str) -> str:
        """Generate YouTube Shorts Title"""
        prompt = f"""
        Create a viral YouTube Shorts title under 99 characters.
        Include trending hashtags. Make it catchy and engaging.

        VIDEO: {video_analysis}

        Only return the title, nothing else.
        """

        try:
            resp = self.client.chat.completions.create(
                model=self.text_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100
            )
            return resp.choices[0].message.content.strip() if resp.choices[0].message.content else "🔥 Viral Moment You Won't Believe! #shorts #viral #trending"
        except:
            return "🔥 Viral Moment You Won't Believe! #shorts #viral #trending"

    def generate_description(self, video_analysis: str) -> str:
        """Generate YouTube Shorts Description"""
        prompt = f"""
        Based on this video:

        {video_analysis}

        Generate a Shorts description:

        - 3-4 lines emotional, engaging intro
        - Then "Keywords:" + 15-20 keywords
        - Then "Tags:" + 15-20  tags
        - Then "Hashtags:" + 15-20 hashtags (must include #shorts, #viral etc.)
        - Then call to action line
        """

        try:
            resp = self.client.chat.completions.create(
                model=self.text_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048
            )
            return resp.choices[0].message.content.strip() if resp.choices[0].message.content else ""
        except Exception as e:
            print("Description Error:", e)
            return ""

    def extract_tags_and_hashtags(self, description: str) -> tuple:
        """Extract tags and hashtags from description"""
        tags = []
        hashtags = []
        
        # Extract hashtags (words starting with #)
        import re
        hashtag_matches = re.findall(r'#\w+', description)
        hashtags = list(set(hashtag_matches))[:30]  # Limit to 30 unique hashtags
        
        # Extract tags from Keywords section
        if "Keywords:" in description:
            keywords_section = description.split("Keywords:")[1].split("Tags:")[0] if "Tags:" in description else description.split("Keywords:")[1]
            keyword_list = [k.strip() for k in keywords_section.split(',')]
            tags.extend(keyword_list[:20])
        
        # Extract from Tags section
        if "Tags:" in description:
            tags_section = description.split("Tags:")[1].split("Hashtags:")[0] if "Hashtags:" in description else description.split("Tags:")[1]
            tag_list = [t.strip() for t in tags_section.split(',')]
            tags.extend(tag_list[:20])
        
        # Clean and deduplicate tags
        tags = [t.strip().replace('#', '') for t in tags if t.strip()]
        tags = list(set(tags))[:30]  # Limit to 30 unique tags
        
        return tags, hashtags

    def generate_complete_metadata(self, video_path: str) -> Dict:
        """Generate full metadata"""
        print("🤖 Analyzing video frames with AI...")
        analysis = self.analyze_video_content(video_path)
        print("📹 Video analysis complete")

        print("🎯 Generating viral shorts title with hashtags...")
        title = self.generate_title(analysis)

        print("📝 Generating description optimized for shorts...")
        description = self.generate_description(analysis)
        
        print("🏷️ Extracting tags and hashtags...")
        tags, hashtags = self.extract_tags_and_hashtags(description)
        
        # ✅ Generate keywords from tags (removing duplicates)
        keywords = list(set([tag.lower() for tag in tags if len(tag) > 2]))[:20]

        return {
            "video_analysis": analysis,
            "title": title,
            "description": description,
            "tags": tags,
            "keywords": keywords,  # ✅ Added keywords
            "hashtags": hashtags,
            "generated_at": datetime.now().isoformat()
        }

    def save_metadata(self, metadata: Dict, output_path: str):
        """Save metadata to JSON file"""
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            print(f"Metadata saved to: {output_path}")
        except Exception as e:
            print("Save Error:", e)


# ---------------- RUNNER -----------------

if __name__ == "__main__":
    generator = AIMetadataGenerator()

    video_path = r"C:\Users\DELL\OneDrive\Desktop\youtube automation ai\downloads\reel_39477079.mp4"

    metadata = generator.generate_complete_metadata(video_path)

    print("\nGenerated Metadata:\n" + "-"*50)
    print("Title:", metadata["title"])
    print("\nDescription:\n", metadata["description"])

    output = r"c:\Users\DELL\OneDrive\Desktop\youtube automation ai\metadata_output.json"
    generator.save_metadata(metadata, output)
