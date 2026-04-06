"""
Database models and operations for AutoTube AI platform.
Uses Firebase Cloud Firestore as the backend.
"""

import os
import logging
from datetime import datetime, timedelta
from firebase_config import db
from google.cloud.firestore_v1 import FieldFilter

logger = logging.getLogger(__name__)

# ─── Collection References ───────────────────────────────────────────────────

USERS_COL = 'users'
TRANSACTIONS_COL = 'transactions'
USAGE_LOG_COL = 'usage_log'


def init_db():
    """No-op for Firestore — collections are created automatically."""
    logger.info("Firestore is schemaless — no initialization required.")


# ─── Helper ──────────────────────────────────────────────────────────────────

def _user_doc_to_dict(doc):
    """Convert a Firestore document snapshot to a user dict."""
    if not doc.exists:
        return None
    data = doc.to_dict()
    data['id'] = doc.id  # Firestore document ID as the user ID
    return data


def _default_user_fields():
    """Default field values for a new user document."""
    return {
        'plan': 'free',
        'tokens_balance': 50,
        'total_tokens_used': 0,
        'total_uploads': 0,
        'success_uploads': 0,
        'avatar_url': '',
        'last_refill': datetime.utcnow().isoformat(),
        'stripe_customer_id': '',
        'youtube_credentials': '',
        'created_at': datetime.utcnow().isoformat(),
    }


# ─── User Operations ────────────────────────────────────────────────────────

def create_user(email, username, password_hash):
    """Create a new user. Returns the Firestore document ID (string)."""
    user_data = _default_user_fields()
    user_data.update({
        'email': email.lower().strip(),
        'username': username.strip(),
        'password_hash': password_hash,
    })
    doc_ref = db.collection(USERS_COL).add(user_data)
    # .add() returns a tuple: (update_time, doc_ref)
    user_id = doc_ref[1].id
    logger.info(f"Created Firestore user: {user_id}")
    return user_id


def get_user_by_email(email):
    """Fetch user by email."""
    docs = (
        db.collection(USERS_COL)
        .where(filter=FieldFilter('email', '==', email.lower().strip()))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _user_doc_to_dict(doc)
    return None


def get_user_by_id(user_id):
    """Fetch user by Firestore document ID."""
    if not user_id:
        return None
    doc = db.collection(USERS_COL).document(str(user_id)).get()
    return _user_doc_to_dict(doc)


def get_user_by_username(username):
    """Fetch user by username."""
    docs = (
        db.collection(USERS_COL)
        .where(filter=FieldFilter('username', '==', username.strip()))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _user_doc_to_dict(doc)
    return None


def update_user(user_id, **fields):
    """Update arbitrary user fields."""
    if not fields:
        return
    db.collection(USERS_COL).document(str(user_id)).update(fields)


def get_youtube_credentials(user_id):
    """Fetch YouTube credentials JSON string for a user."""
    user = get_user_by_id(user_id)
    if user and user.get('youtube_credentials'):
        return user['youtube_credentials']
    return None


def update_youtube_credentials(user_id, credentials_json):
    """Update YouTube credentials JSON string for a user."""
    db.collection(USERS_COL).document(str(user_id)).update({
        'youtube_credentials': credentials_json or ''
    })


# ─── Token Operations ────────────────────────────────────────────────────────

def deduct_tokens(user_id, amount, action, task_id='', details=''):
    """Deduct tokens and log usage. Returns False if insufficient balance."""
    user_ref = db.collection(USERS_COL).document(str(user_id))
    user_doc = user_ref.get()
    if not user_doc.exists:
        return False

    user_data = user_doc.to_dict()
    if user_data.get('tokens_balance', 0) < amount:
        return False

    # Update user tokens
    user_ref.update({
        'tokens_balance': user_data['tokens_balance'] - amount,
        'total_tokens_used': user_data.get('total_tokens_used', 0) + amount,
    })

    # Log usage
    db.collection(USAGE_LOG_COL).add({
        'user_id': str(user_id),
        'action': action,
        'tokens_used': amount,
        'task_id': task_id,
        'details': details,
        'created_at': datetime.utcnow().isoformat(),
    })
    return True


def add_tokens(user_id, amount):
    """Add tokens to user balance."""
    user_ref = db.collection(USERS_COL).document(str(user_id))
    user_doc = user_ref.get()
    if user_doc.exists:
        current = user_doc.to_dict().get('tokens_balance', 0)
        user_ref.update({'tokens_balance': current + amount})


def increment_uploads(user_id, success=True):
    """Increment upload counters."""
    user_ref = db.collection(USERS_COL).document(str(user_id))
    user_doc = user_ref.get()
    if not user_doc.exists:
        return

    data = user_doc.to_dict()
    updates = {'total_uploads': data.get('total_uploads', 0) + 1}
    if success:
        updates['success_uploads'] = data.get('success_uploads', 0) + 1
    user_ref.update(updates)


# ─── Transaction Operations ──────────────────────────────────────────────────

def create_transaction(user_id, amount_cents, tokens_purchased,
                       plan_purchased='', stripe_session_id=''):
    """Record a payment transaction."""
    db.collection(TRANSACTIONS_COL).add({
        'user_id': str(user_id),
        'amount_cents': amount_cents,
        'tokens_purchased': tokens_purchased,
        'plan_purchased': plan_purchased,
        'stripe_session_id': stripe_session_id,
        'status': 'completed',
        'created_at': datetime.utcnow().isoformat(),
    })


def get_transactions(user_id, limit=20):
    """Get recent transactions for a user."""
    docs = (
        db.collection(TRANSACTIONS_COL)
        .where(filter=FieldFilter('user_id', '==', str(user_id)))
        .stream()
    )
    results = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        results.append(d)
    
    results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return results[:limit]


# ─── Usage / Stats ────────────────────────────────────────────────────────────

def get_usage_log(user_id, limit=50):
    """Get recent usage log entries."""
    docs = (
        db.collection(USAGE_LOG_COL)
        .where(filter=FieldFilter('user_id', '==', str(user_id)))
        .stream()
    )
    results = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        results.append(d)
        
    results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return results[:limit]


def get_user_stats(user_id):
    """Get aggregated stats for dashboard."""
    user = get_user_by_id(user_id)
    if not user:
        return None

    today = datetime.utcnow().strftime('%Y-%m-%d')
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')

    # Fetch all logs for this user to avoid composite index requirements
    all_logs_stream = (
        db.collection(USAGE_LOG_COL)
        .where(filter=FieldFilter('user_id', '==', str(user_id)))
        .stream()
    )

    today_uploads = 0
    tokens_today = 0
    daily_map = {}

    for doc in all_logs_stream:
        d = doc.to_dict()
        created_at = d.get('created_at', '')
        
        # Today stats
        if created_at >= today:
            if d.get('action') == 'upload':
                today_uploads += 1
            tokens_today += d.get('tokens_used', 0)
            
        # Week stats
        if created_at >= week_ago:
            day = created_at[:10]
            daily_map[day] = daily_map.get(day, 0) + d.get('tokens_used', 0)

    daily_usage = [{'day': k, 'tokens': v} for k, v in sorted(daily_map.items())]

    total_uploads = user.get('total_uploads', 0)
    success_uploads = user.get('success_uploads', 0)

    return {
        'tokens_balance': user.get('tokens_balance', 0),
        'total_tokens_used': user.get('total_tokens_used', 0),
        'total_uploads': total_uploads,
        'success_uploads': success_uploads,
        'success_rate': round((success_uploads / max(total_uploads, 1)) * 100),
        'plan': user.get('plan', 'free'),
        'uploads_today': today_uploads,
        'tokens_today': tokens_today,
        'daily_usage': daily_usage,
    }


def get_recent_uploads(user_id, limit=10):
    """Get recent upload entries from usage log."""
    docs = (
        db.collection(USAGE_LOG_COL)
        .where(filter=FieldFilter('user_id', '==', str(user_id)))
        .stream()
    )
    results = []
    for doc in docs:
        d = doc.to_dict()
        if d.get('action') == 'upload':
            d['id'] = doc.id
            results.append(d)
            
    results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return results[:limit]
