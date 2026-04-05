"""
Firebase Admin SDK initialization for AutoTube AI.
Initializes Firestore client using the service account key.
"""

import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Locate Service Account Key ──────────────────────────────────────────────

_KEY_PATHS = [
    os.path.join(BASE_DIR, 'serviceAccountKey.json'),
    os.path.join(os.path.dirname(BASE_DIR), 'serviceAccountKey.json'),
    '/etc/secrets/serviceAccountKey.json',            # Render secret file
]


def _find_key():
    """Find the service account key file or parse it from env var."""
    for path in _KEY_PATHS:
        if os.path.exists(path):
            logger.info(f"Using Firebase key from: {path}")
            return credentials.Certificate(path)

    # Fallback: key content stored in environment variable (Render / Docker)
    key_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY')
    if key_json:
        try:
            key_data = json.loads(key_json)
            logger.info("Using Firebase key from FIREBASE_SERVICE_ACCOUNT_KEY env var")
            return credentials.Certificate(key_data)
        except json.JSONDecodeError:
            logger.error("FIREBASE_SERVICE_ACCOUNT_KEY env var contains invalid JSON")

    raise FileNotFoundError(
        "Firebase service account key not found. "
        "Place serviceAccountKey.json in the project root or set FIREBASE_SERVICE_ACCOUNT_KEY env var."
    )


# ─── Initialize Firebase ─────────────────────────────────────────────────────

def init_firebase():
    """Initialize the Firebase app (idempotent — safe to call multiple times)."""
    if not firebase_admin._apps:
        cred = _find_key()
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully")
    return firestore.client()


# Module-level Firestore client (lazy singleton)
db = init_firebase()
