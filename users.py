"""
users.py - Simple JSON-file-based user storage
--------------------------------------------------
Not production-grade (a real app would use a proper database), but
sufficient for a student project demo. Passwords are hashed, never
stored in plain text.
"""

import json
import os
from werkzeug.security import generate_password_hash, check_password_hash

USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")


def _load():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def _save(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def create_user(phone, password, email):
    users = _load()
    if phone in users:
        return False, "An account with this phone number already exists."
    users[phone] = {
        "password_hash": generate_password_hash(password),
        "email": email,
    }
    _save(users)
    return True, "Account created."


def verify_user(phone, password):
    users = _load()
    user = users.get(phone)
    if not user:
        return False
    return check_password_hash(user["password_hash"], password)


def get_all_emails():
    """Returns every registered user's email, for broadcasting peak alerts."""
    users = _load()
    return [u["email"] for u in users.values() if u.get("email")]
