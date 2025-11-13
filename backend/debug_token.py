"""Debug token creation and validation."""
import os
from dotenv import load_dotenv
from services.auth_service import create_access_token, verify_token

load_dotenv()

print("=" * 60)
print("JWT SECRET KEY CHECK")
print("=" * 60)
print(f"JWT_SECRET_KEY: {os.getenv('JWT_SECRET_KEY')}")
print()

# Create a test token
print("Creating test token...")
test_data = {"sub": 1, "role": "customer"}
token = create_access_token(test_data)
print(f"Token created: {token[:50]}...")
print()

# Try to verify it
print("Verifying token...")
result = verify_token(token)
print(f"Verification result: {result}")
print()

if result:
    print("✅ Token verification WORKS!")
else:
    print("❌ Token verification FAILED!")
    print("\nThis means the JWT_SECRET_KEY used to create the token")
    print("is different from the one used to verify it.")
    print("\nCheck:")
    print("1. Is .env file in the backend directory?")
    print("2. Did you restart the server after creating .env?")
    print("3. Is JWT_SECRET_KEY set in .env?")

