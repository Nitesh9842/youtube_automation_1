"""
Database initialization script.
Run this to create or reset the database.
"""
from models import init_db, DB_PATH
import os

if __name__ == '__main__':
    if os.path.exists(DB_PATH):
        print(f"⚠️  Database already exists at: {DB_PATH}")
        choice = input("   Reset? (y/N): ").strip().lower()
        if choice == 'y':
            os.remove(DB_PATH)
            print("   Removed old database.")
        else:
            print("   Keeping existing database.")

    init_db()
    print(f"✅ Database initialized at: {DB_PATH}")
