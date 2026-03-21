"""
WSGI entry point for Gunicorn / production servers.

Usage:
    gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
"""

from app import app

if __name__ == "__main__":
    app.run()
