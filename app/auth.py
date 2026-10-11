import hashlib
import hmac
import secrets
import time

from sqlalchemy import delete, select

from app.library import DEFAULT_CATEGORIES, category
from app.models import Admin, BrowserSession, ImportPreview, LoginLimit


def password_hash(password):
    if not 12 <= len(password) <= 256:
        raise ValueError("Usa una contraseña de entre 12 y 256 caracteres.")
    salt = secrets.token_hex(16)
    value = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64 * 1024 * 1024
    )
    return f"scrypt$32768$8$1${salt}${value.hex()}"


def verify_password(password, encoded):
    if len(password) > 256:
        return False
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), maxmem=64 * 1024 * 1024
        )
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def initialize(db, settings):
    if not db.scalar(select(Admin)):
        username = settings.initial_user.strip()
        if not username or len(username) > 80:
            raise RuntimeError(
                "Primer arranque: define INITIAL_ADMIN_USER y INITIAL_ADMIN_PASSWORD (mínimo 12 caracteres)."
            )
        db.add(Admin(id=1, username=username, password_hash=password_hash(settings.initial_password)))
        for name in DEFAULT_CATEGORIES:
            category(db, name)
        db.commit()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(db, hours, authenticated=False):
    token = secrets.token_urlsafe(32)
    session = BrowserSession(
        token_hash=token_hash(token),
        csrf=secrets.token_urlsafe(32),
        authenticated=authenticated,
        expires_at=int(time.time()) + hours * 3600,
    )
    db.execute(delete(BrowserSession).where(BrowserSession.expires_at < int(time.time())))
    db.execute(delete(ImportPreview).where(ImportPreview.expires_at < int(time.time())))
    db.add(session)
    db.commit()
    return token, session


def consume_limit(db, key, maximum, seconds):
    # BEGIN IMMEDIATE makes increments atomic across request threads (one app instance).
    db.rollback()
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    current = int(time.time())
    item = db.get(LoginLimit, key)
    if not item:
        item = LoginLimit(key=key, count=0, reset_at=current + seconds)
        db.add(item)
    elif item.reset_at <= current:
        item.count, item.reset_at = 0, current + seconds
    if item.count >= maximum:
        db.rollback()
        return False
    item.count += 1
    db.commit()
    return True
