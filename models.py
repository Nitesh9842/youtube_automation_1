"""
Database models and operations for YouTube Automation platform.
Uses SQLite for simplicity — swap to PostgreSQL for production scale.
"""

import sqlite3
import os
import time
from datetime import datetime, timedelta
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                email           TEXT UNIQUE NOT NULL,
                username        TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL,
                plan            TEXT DEFAULT 'free' CHECK(plan IN ('free','pro','enterprise')),
                tokens_balance  INTEGER DEFAULT 50,
                total_tokens_used INTEGER DEFAULT 0,
                total_uploads   INTEGER DEFAULT 0,
                success_uploads INTEGER DEFAULT 0,
                avatar_url      TEXT DEFAULT '',
                last_refill     TEXT DEFAULT (datetime('now')),
                stripe_customer_id TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                amount_cents    INTEGER NOT NULL,
                tokens_purchased INTEGER NOT NULL,
                plan_purchased  TEXT DEFAULT '',
                stripe_session_id TEXT DEFAULT '',
                status          TEXT DEFAULT 'completed',
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS usage_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                action          TEXT NOT NULL,
                tokens_used     INTEGER NOT NULL,
                task_id         TEXT DEFAULT '',
                details         TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_log(user_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
        """)


# ─── User Operations ─────────────────────────────────────────────────────────

def create_user(email, username, password_hash):
    """Create a new user. Returns the user id."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)",
            (email.lower().strip(), username.strip(), password_hash)
        )
        return cursor.lastrowid


def get_user_by_email(email):
    """Fetch user by email."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    """Fetch user by id."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_username(username):
    """Fetch user by username."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
        return dict(row) if row else None


def update_user(user_id, **fields):
    """Update arbitrary user fields."""
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [user_id]
    with get_db() as conn:
        conn.execute(f"UPDATE users SET {sets} WHERE id = ?", vals)


# ─── Token Operations ────────────────────────────────────────────────────────

def deduct_tokens(user_id, amount, action, task_id='', details=''):
    """Deduct tokens and log usage. Returns False if insufficient balance."""
    with get_db() as conn:
        user = conn.execute(
            "SELECT tokens_balance FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user or user['tokens_balance'] < amount:
            return False
        conn.execute(
            "UPDATE users SET tokens_balance = tokens_balance - ?, "
            "total_tokens_used = total_tokens_used + ? WHERE id = ?",
            (amount, amount, user_id)
        )
        conn.execute(
            "INSERT INTO usage_log (user_id, action, tokens_used, task_id, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, action, amount, task_id, details)
        )
        return True


def add_tokens(user_id, amount):
    """Add tokens to user balance."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET tokens_balance = tokens_balance + ? WHERE id = ?",
            (amount, user_id)
        )


def increment_uploads(user_id, success=True):
    """Increment upload counters."""
    with get_db() as conn:
        if success:
            conn.execute(
                "UPDATE users SET total_uploads = total_uploads + 1, "
                "success_uploads = success_uploads + 1 WHERE id = ?",
                (user_id,)
            )
        else:
            conn.execute(
                "UPDATE users SET total_uploads = total_uploads + 1 WHERE id = ?",
                (user_id,)
            )


# ─── Transaction Operations ──────────────────────────────────────────────────

def create_transaction(user_id, amount_cents, tokens_purchased,
                       plan_purchased='', stripe_session_id=''):
    """Record a payment transaction."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO transactions "
            "(user_id, amount_cents, tokens_purchased, plan_purchased, stripe_session_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount_cents, tokens_purchased, plan_purchased, stripe_session_id)
        )


def get_transactions(user_id, limit=20):
    """Get recent transactions for a user."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Usage / Stats ────────────────────────────────────────────────────────────

def get_usage_log(user_id, limit=50):
    """Get recent usage log entries."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM usage_log WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_stats(user_id):
    """Get aggregated stats for dashboard."""
    with get_db() as conn:
        user = conn.execute(
            "SELECT tokens_balance, total_tokens_used, total_uploads, success_uploads, plan "
            "FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return None

        # Uploads today
        today = datetime.utcnow().strftime('%Y-%m-%d')
        today_count = conn.execute(
            "SELECT COUNT(*) as c FROM usage_log "
            "WHERE user_id = ? AND action = 'upload' AND created_at LIKE ?",
            (user_id, f'{today}%')
        ).fetchone()['c']

        # Tokens used today
        tokens_today = conn.execute(
            "SELECT COALESCE(SUM(tokens_used), 0) as t FROM usage_log "
            "WHERE user_id = ? AND created_at LIKE ?",
            (user_id, f'{today}%')
        ).fetchone()['t']

        # Last 7 days usage
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        daily_usage = conn.execute(
            "SELECT DATE(created_at) as day, SUM(tokens_used) as tokens "
            "FROM usage_log WHERE user_id = ? AND created_at >= ? "
            "GROUP BY DATE(created_at) ORDER BY day",
            (user_id, week_ago)
        ).fetchall()

        return {
            'tokens_balance': user['tokens_balance'],
            'total_tokens_used': user['total_tokens_used'],
            'total_uploads': user['total_uploads'],
            'success_uploads': user['success_uploads'],
            'success_rate': round(
                (user['success_uploads'] / max(user['total_uploads'], 1)) * 100
            ),
            'plan': user['plan'],
            'uploads_today': today_count,
            'tokens_today': tokens_today,
            'daily_usage': [dict(d) for d in daily_usage],
        }


def get_recent_uploads(user_id, limit=10):
    """Get recent upload entries from usage log."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM usage_log WHERE user_id = ? AND action = 'upload' "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# Initialize on import
init_db()
