import argparse

from app.core.security import create_access_token
from app.schemas.auth import UserToken


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
