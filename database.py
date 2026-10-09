"""Everything that reads or writes the SQLite database."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

import config
import security


@contextmanager
def _db():
    """Open the database, save changes at the end, always close it."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row          # rows work like dictionaries
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    """Create tables, and create the default admin on the very first run."""
    with _db() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   username TEXT UNIQUE NOT NULL,
                   full_name TEXT NOT NULL,
                   password_hash TEXT NOT NULL,
                   role TEXT NOT NULL DEFAULT 'user',        -- 'admin' or 'user'
                   status TEXT NOT NULL DEFAULT 'pending',   -- 'pending', 'approved', 'rejected'
                   face_data BLOB,                           -- encrypted face encoding (or NULL)
                   must_change_password INTEGER NOT NULL DEFAULT 0,
                   created_at TEXT NOT NULL)"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS access_logs (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   time TEXT NOT NULL,
                   user_id INTEGER,
                   name TEXT NOT NULL,
                   result TEXT NOT NULL,                     -- 'GRANTED' or 'DENIED'
                   reason TEXT NOT NULL)"""
        )
        if "hand_data" not in [r["name"] for r in db.execute("PRAGMA table_info(users)")]:
            db.execute("ALTER TABLE users ADD COLUMN hand_data BLOB")   # added in a later version
        has_admin = db.execute("SELECT 1 FROM users WHERE role = 'admin'").fetchone()
    if not has_admin:
        create_user(config.DEFAULT_ADMIN_USERNAME, "Administrator",
                    config.DEFAULT_ADMIN_PASSWORD, role="admin",
                    status="approved", must_change=True)


# ---------- users ----------
def create_user(username, full_name, password, role="user", status="pending", must_change=False):
    """Add a user. Returns the new id. Raises ValueError if the username is taken."""
    try:
        with _db() as db:
            cur = db.execute(
                """INSERT INTO users (username, full_name, password_hash, role, status,
                                      must_change_password, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (username, full_name, generate_password_hash(password), role, status,
                 int(must_change), _now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"Username '{username}' is already taken.")


def get_user(user_id):
    with _db() as db:
        return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_username(username):
    with _db() as db:
        return db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def check_login(username, password):
    """Returns the user row if the password is right, otherwise None."""
    user = get_user_by_username(username)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def list_users():
    with _db() as db:
        return db.execute(
            "SELECT id, username, full_name, status, face_data IS NOT NULL AS has_face, hand_data IS NOT NULL AS has_hand, created_at "
            "FROM users WHERE role = 'user' ORDER BY id DESC"
        ).fetchall()


def set_status(user_id, status):
    with _db() as db:
        db.execute("UPDATE users SET status = ? WHERE id = ? AND role = 'user'", (status, user_id))


def set_password(user_id, new_password, must_change=False):
    with _db() as db:
        db.execute("UPDATE users SET password_hash = ?, must_change_password = ? WHERE id = ?",
                   (generate_password_hash(new_password), int(must_change), user_id))


def set_face(user_id, encoding):
    """Save the (encrypted) face of a user."""
    with _db() as db:
        db.execute("UPDATE users SET face_data = ? WHERE id = ?",
                   (security.encrypt_encoding(encoding), user_id))


def set_hand(user_id, features):
    """Save the (encrypted) hand shape of a user."""
    with _db() as db:
        db.execute("UPDATE users SET hand_data = ? WHERE id = ?",
                   (security.encrypt_encoding(features), user_id))


def get_hand(user_id):
    """The user's saved hand shape, or None if no hand is registered."""
    user = get_user(user_id)
    return security.decrypt_encoding(user["hand_data"]) if user and user["hand_data"] else None


def delete_user(user_id):
    """Delete a normal user (admins cannot be deleted). Returns True if deleted."""
    with _db() as db:
        cur = db.execute("DELETE FROM users WHERE id = ? AND role = 'user'", (user_id,))
        return cur.rowcount > 0


def get_face_users():
    """Approved accounts (users and admins) with a face: list of (user_id, username, encoding). Used for matching."""
    with _db() as db:
        rows = db.execute(
            "SELECT id, username, face_data FROM users "
            "WHERE status = 'approved' AND face_data IS NOT NULL"
        ).fetchall()
    return [(r["id"], r["username"], security.decrypt_encoding(r["face_data"])) for r in rows]


# ---------- logs ----------
def log_attempt(name, result, reason, user_id=None):
    """Record one access attempt. result = 'GRANTED' or 'DENIED'."""
    with _db() as db:
        db.execute(
            "INSERT INTO access_logs (time, user_id, name, result, reason) VALUES (?, ?, ?, ?, ?)",
            (_now(), user_id, name, result, reason),
        )


def get_logs(result=None, search=None, limit=500):
    """Newest first. Optional filters: result ('GRANTED'/'DENIED') and name search."""
    sql, params = "SELECT * FROM access_logs WHERE 1=1", []
    if result in ("GRANTED", "DENIED"):
        sql += " AND result = ?"
        params.append(result)
    if search:
        sql += " AND name LIKE ?"
        params.append(f"%{search}%")
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _db() as db:
        return db.execute(sql, params).fetchall()


def get_user_logs(user_id, limit=50):
    with _db() as db:
        return db.execute("SELECT * FROM access_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                          (user_id, limit)).fetchall()


def get_stats():
    """Numbers for the admin dashboard."""
    today = datetime.now().strftime("%Y-%m-%d")
    with _db() as db:
        one = lambda sql, *p: db.execute(sql, p).fetchone()[0]
        return {
            "users": one("SELECT COUNT(*) FROM users WHERE role = 'user'"),
            "pending": one("SELECT COUNT(*) FROM users WHERE role = 'user' AND status = 'pending'"),
            "granted": one("SELECT COUNT(*) FROM access_logs WHERE result = 'GRANTED'"),
            "denied": one("SELECT COUNT(*) FROM access_logs WHERE result = 'DENIED'"),
            "today": one("SELECT COUNT(*) FROM access_logs WHERE time LIKE ?", today + "%"),
        }
