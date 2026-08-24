"""
Creates a single user with a given role. Use this any time you need a new
Admin or normal User account beyond the one default admin created by
seed_initial_data.py.

Usage:
    python -m app.scripts.create_user <username> <password> <role>

    role must be exactly 'admin' or 'user'.

Examples:
    python -m app.scripts.create_user viewer viewer123 user
    python -m app.scripts.create_user supervisor supervisor123 admin

If the username already exists, its password and role are updated instead
of creating a duplicate (so this also doubles as a password-reset tool).
"""
import sys
import logging

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.auth.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    username, password, role_str = sys.argv[1], sys.argv[2], sys.argv[3].lower()

    if role_str not in ("admin", "user"):
        print(f"Invalid role '{role_str}' - must be 'admin' or 'user'")
        sys.exit(1)

    role = UserRole.ADMIN if role_str == "admin" else UserRole.USER

    db = SessionLocal()
    try:
        existing = db.query(User).filter_by(username=username).one_or_none()
        if existing:
            existing.hashed_password = hash_password(password)
            existing.role = role
            db.commit()
            logger.info("Updated existing user '%s' (role=%s, password reset)", username, role.value)
        else:
            db.add(User(username=username, hashed_password=hash_password(password), role=role))
            db.commit()
            logger.info("Created user '%s' with role=%s", username, role.value)
    finally:
        db.close()


if __name__ == "__main__":
    main()
