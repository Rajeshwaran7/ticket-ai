"""Test authentication endpoint."""
import requests
import json

BASE_URL = "http://localhost:8000"

# Test registration
print("Testing registration...")
register_data = {
    "email": "testcustomer@test.com",
    "username": "testcustomer",
    "password": "test123",
    "full_name": "Test Customer",
    "role": "customer"
}

response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

if response.status_code == 201:
    token = response.json()["access_token"]
    print(f"\nToken: {token[:50]}...")
    
    # Test creating ticket with token
    print("\n\nTesting ticket creation with token...")
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    ticket_data = {
        "message": "Test ticket message",
        "customer": "Test Customer"
    }
    
    # Try multipart form data
    response2 = requests.post(
        f"{BASE_URL}/api/ticket/chat",
        data=ticket_data,
        headers=headers
    )
    print(f"Status: {response2.status_code}")
    print(f"Response: {response2.text}")

