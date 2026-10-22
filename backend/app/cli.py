"""Local operator command. Does not expose an API for promoting administrators."""
import argparse
from .database import SessionLocal
from .models import User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['make-admin'])
    parser.add_argument('user_id', help='ID of an already registered, trusted club officer')
    args = parser.parse_args()
    with SessionLocal() as db:
        user = db.get(User, args.user_id)
        if not user:
            parser.error('No registered user has that ID.')
        user.is_admin = True
        db.commit()
        print(f'Officer access granted to {user.name} ({user.id}).')


if __name__ == '__main__':
    main()
