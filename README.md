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

AI-powered automation tool for downloading Instagram Reels, generating metadata with Google Gemini AI, and uploading to YouTube automatically.

## ✨ Features

- 📥 **Instagram Reel Downloader**: Download Reels in HD quality with original audio
- 🤖 **AI Metadata Generator**: Generate SEO-optimized titles, descriptions, tags using Google Gemini 2.0
- 📤 **YouTube Auto Uploader**: Upload directly to YouTube with automated metadata
- 🎵 **Video Editor**: Add background music and text overlays to videos
- 🔐 **Multi-User Support**: Each user has their own isolated YouTube authentication

## 🚀 Quick Start

1. **Set Environment Variables** (Required):
   - `GEMINI_API_KEY`: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - `IG_SESSIONID`: Instagram session cookie (see below)
   - `SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_hex(32))"`

2. **Upload client_secret.json**:
   - Create OAuth credentials in [Google Cloud Console](https://console.cloud.google.com)
   - Enable YouTube Data API v3
   - Download and upload `client_secret.json` as a secret file

3. **Access the app** and start automating!

## 🔑 Getting Instagram Session ID

1. Open Instagram in Chrome
2. Press `F12` → Application → Cookies → instagram.com
3. Find `sessionid` cookie and copy its value
4. Add to Space secrets as `IG_SESSIONID`

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
- **AI**: Google Gemini 2.0 Flash
- **APIs**: YouTube Data API v3, Instagram
- **Video Processing**: MoviePy, OpenCV, FFmpeg
- **Auth**: OAuth 2.0, Session-based authentication

## 📋 Environment Variables

Set these in your Hugging Face Space settings:

```env
ENVIRONMENT=production
GEMINI_API_KEY=your-gemini-api-key-here
IG_SESSIONID=your-instagram-sessionid-here
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
