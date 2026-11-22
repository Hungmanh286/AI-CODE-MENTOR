"""Generate a JWT access token signed with SECRET_KEY from .env.

    uv run python scripts/gen_token.py --user-id 000000 --username Tester01
    uv run python -m scripts.gen_token --user-id 000000 --username Tester01
"""

import argparse
import sys
from pathlib import Path

# Running by path puts scripts/ (not the repo root) on sys.path; add the root so `app` imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import create_access_token  # noqa: E402
from app.schemas.auth import UserToken  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Generate a JWT access token for AI-CODE-MENTOR")
    parser.add_argument("--user-id", default="000000", help="User ID (default: 000000)")
    parser.add_argument("--username", default="Tester01", help="Username (default: Tester01)")
    parser.add_argument("--limit", type=int, default=1000000, help="Token limit (default: 1000000)")

    args = parser.parse_args()

    user_token = UserToken(
        user_id=args.user_id,
        username=args.username,
        token_limit=args.limit
    )

    token = create_access_token(user_token.model_dump())
    print("\n--- GENERATED TOKEN ---")
    print(token)
    print("-----------------------\n")

if __name__ == "__main__":
    main()
