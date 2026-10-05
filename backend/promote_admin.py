"""
backend/promote_admin.py
────────────────────────
One-time CLI script to promote a Firebase Auth user to admin.

Usage:
    python promote_admin.py <email>

Example:
    python promote_admin.py karthikeya@example.com
"""

import sys

from config import Config  # noqa: F401 — triggers dotenv loading
import db


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python promote_admin.py <email>")
        print("Example: python promote_admin.py admin@example.com")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    print(f"Promoting {email} to admin...")

    # Initialise Firebase
    db.init_firestore()

    from firebase_admin import auth as fb_auth

    try:
        user = fb_auth.get_user_by_email(email)
    except fb_auth.UserNotFoundError:
        print(f"ERROR: No Firebase Auth user found with email: {email}")
        print("Make sure the user has signed in at least once.")
        sys.exit(1)

    db.set_admin_claim(user.uid)

    print(f"SUCCESS: {email} (uid={user.uid}) is now an admin.")
    print("The user must sign out and sign back in for the change to take effect.")


if __name__ == '__main__':
    main()
