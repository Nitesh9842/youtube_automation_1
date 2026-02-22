---
title: YouTube Automation Studio
emoji: 🎬
colorFrom: red
colorTo: blue
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# 🎬 YouTube Automation Studio

AI-powered automation tool for downloading Instagram Reels, generating metadata with Groq AI, and uploading to YouTube automatically.

## ✨ Features

- 📥 **Instagram Reel Downloader**: Download Reels in HD quality with original audio using RapidAPI
- 🤖 **AI Metadata Generator**: Generate SEO-optimized titles, descriptions, tags using Groq AI
- 📤 **YouTube Auto Uploader**: Upload directly to YouTube with automated metadata
- 🎵 **Video Editor**: Add background music and text overlays to videos
- 🔐 **Multi-User Support**: Each user has their own isolated YouTube authentication

## 🚀 Quick Start

1. **Set Environment Variables** (Required):
   - `GROQ_API_KEY`: Get from [Groq Console](https://console.groq.com/)
   - `RAPIDAPI_KEY`: Get from [RapidAPI Instagram Downloader](https://rapidapi.com/hub)
   - `SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_hex(32))"`

2. **Upload client_secret.json**:
   - Create OAuth credentials in [Google Cloud Console](https://console.cloud.google.com)
   - Enable YouTube Data API v3
   - Download and upload `client_secret.json` as a secret file

3. **Access the app** and start automating!

## 🔑 Getting API Keys

### Groq API Key (for AI metadata generation)
1. Visit [Groq Console](https://console.groq.com/)
2. Create an account and get your API key
3. Add to environment as `GROQ_API_KEY`

### RapidAPI Key (for Instagram downloads)
1. Visit [RapidAPI](https://rapidapi.com/)
2. Subscribe to an Instagram downloader API
3. Add to environment as `RAPIDAPI_KEY`

## 🎯 Usage

1. **Sign in with YouTube** (OAuth 2.0 - secure & one-time)
2. **Paste Instagram Reel URL**
3. **(Optional) Add video editing**:
   - Background music from YouTube or local file
   - Text overlays with custom positioning
4. **AI generates metadata** (title, description, tags, hashtags)
5. **Video uploads to YouTube** automatically

## 🛠️ Tech Stack

- **Backend**: Flask, Python 3.11, Gunicorn
- **AI**: Groq AI (Llama 4 Scout Vision & Llama 3.3 70B)
- **APIs**: YouTube Data API v3, RapidAPI Instagram Downloader
- **Video Processing**: MoviePy, OpenCV, FFmpeg
- **Auth**: OAuth 2.0, Session-based authentication

## 📋 Environment Variables

Set these in your deployment platform settings:

```env
ENVIRONMENT=production
GROQ_API_KEY=your-groq-api-key-here
RAPIDAPI_KEY=your-rapidapi-key-here
SECRET_KEY=your-secret-key-here
```

## 🔒 Security

- OAuth 2.0 for YouTube authentication
- Session-based user isolation
- Secure cookie handling
- No password storage
- Automatic credential refresh

## 📝 OAuth Redirect URI

Add this to your Google Cloud OAuth credentials:
````

# Youtube-Automation2
