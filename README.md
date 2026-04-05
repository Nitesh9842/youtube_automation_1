# 🎬 AutoTube AI Platform

A full-stack web application that automates the process of downloading, editing, and uploading videos to YouTube — powered by AI-generated metadata.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

| Feature | Description |
|---|---|
| 📥 **Instagram Downloader** | Download reels directly from Instagram URLs via RapidAPI (multi-endpoint fallback) |
| 🎞️ **Video Editor** | Add background music (YouTube/local), text overlays, and more using FFmpeg |
| 🤖 **AI Metadata** | Auto-generate viral titles, descriptions, tags & hashtags using Groq Vision + LLaMA |
| 📤 **YouTube Upload** | One-click upload to YouTube with OAuth 2.0 authentication |
| 🔐 **Auth System** | Full user registration, login, and profile management with bcrypt hashing |
| 🪙 **Token Economy** | Usage-based token system with daily refills and multiple pricing plans |
| 💳 **Stripe Payments** | Plan upgrades and token top-up packs (works in mock mode without API keys) |
| 📊 **Dashboard** | Track upload stats, token balance, and recent activity |

---

## 🏗️ Tech Stack

- **Backend:** Flask, Gunicorn, Flask-Login, Flask-Session
- **AI:** Groq SDK (LLaMA 4 Scout for vision, LLaMA 3.3 70B for text)
- **Video:** FFmpeg, OpenCV, Pillow, yt-dlp
- **Payments:** Stripe (optional)
- **Database:** SQLite
- **Auth:** bcrypt, Google OAuth 2.0 (YouTube)

---

## 📁 Project Structure

```
youtube_automation_1/
├── app.py              # Main Flask application & routes
├── auth.py             # Authentication blueprint (register/login/logout)
├── payments.py         # Stripe payments blueprint
├── token_system.py     # Token economy (plans, costs, refills)
├── models.py           # Database models & queries (SQLite)
├── init_db.py          # Database initialization script
├── downloader.py       # Instagram reel downloader (RapidAPI)
├── ai_genrator.py      # AI metadata generator (Groq Vision + LLM)
├── video_editor.py     # Video editing pipeline (FFmpeg)
├── uploader.py         # YouTube upload via Google API
├── requirements.txt    # Python dependencies
├── templates/          # Jinja2 HTML templates
├── static/             # CSS, JS, images
├── downloads/          # Temporary video downloads
└── user_tokens/        # Per-user YouTube OAuth tokens
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **FFmpeg** — required for video editing
  - Windows: `choco install ffmpeg` or `winget install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd youtube_automation_1
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Required
GROQ_API_KEY=your_groq_api_key
RAPIDAPI_KEY=your_rapidapi_key

# Optional
SECRET_KEY=your_flask_secret_key
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
ENVIRONMENT=development

# YouTube OAuth
GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/auth/callback
```

> You also need a `client_secret.json` file from the [Google Cloud Console](https://console.cloud.google.com/) with YouTube Data API v3 enabled.

### 5. Initialize the Database

```bash
python init_db.py
```

### 6. Run the Application

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## 🔑 API Keys Setup

| Service | Purpose | Link |
|---|---|---|
| **Groq** | AI video analysis & metadata generation | [console.groq.com](https://console.groq.com) |
| **RapidAPI** | Instagram reel downloading | [rapidapi.com](https://rapidapi.com) |
| **Google Cloud** | YouTube OAuth & upload | [console.cloud.google.com](https://console.cloud.google.com) |
| **Stripe** *(optional)* | Payment processing | [dashboard.stripe.com](https://dashboard.stripe.com) |

---

## 🪙 Token System & Pricing

| Action | Token Cost |
|---|---|
| Upload to YouTube | 5 tokens |
| AI Video Analysis | 3 tokens |
| Video Editing | 4 tokens |
| Download | 2 tokens |

| Plan | Price | Monthly Tokens | Daily Refill |
|---|---|---|---|
| Free | $0 | 50 | 10/day |
| Pro | $9.99/mo | 500 | 25/day |
| Enterprise | $29.99/mo | 2,000 | 100/day |

---

## 🔄 Upload Pipeline

```
Instagram URL / Local File
        │
        ▼
   ┌─────────┐
   │ Download │  (RapidAPI with fallback endpoints)
   └────┬────┘
        ▼
   ┌─────────┐
   │  Edit    │  (FFmpeg: music, text overlays)
   └────┬────┘
        ▼
   ┌──────────┐
   │ AI Analyze│  (Groq Vision → title, desc, tags)
   └────┬─────┘
        ▼
   ┌──────────┐
   │  Upload   │  (YouTube Data API v3)
   └──────────┘
```

---

## ☁️ Deployment

The app detects cloud environments (Render, Heroku, Railway, Docker) automatically. For production:

1. Set `ENVIRONMENT=production` in your env vars
2. Use Gunicorn: `gunicorn app:app --bind 0.0.0.0:$PORT`
3. Ensure FFmpeg is installed on the server (add `ffmpeg` to `Aptfile` or `packages.txt`)
4. Set `GOOGLE_REDIRECT_URI` to your production callback URL

---

## 📄 License

This project is open source under the [MIT License](LICENSE).
