#!/usr/bin/env python
"""
Example script demonstrating how to send invitation emails using the OneSignal MCP server.
This showcases the functionality that replaces SendGrid's invitation system.
"""
import asyncio
import sys
import os

# Add the parent directory to the path so we can import the server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the server module
from onesignal_server import send_invite_email, send_bulk_invites

async def send_single_invite():
    """Send a single invitation email."""
    print("Sending a single invitation email...")
    
    result = await send_invite_email(
        email="recipient@example.com",
        first_name="John",
        invite_url="https://yourapp.com/invite/abc123",
        inviter_name="Jane Smith",
        app_name="Your Amazing App",
        expiry_days=7
    )
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Success! Email sent to recipient@example.com")
        print(f"Details: {result}")

async def send_multiple_invites():
    """Send multiple invitation emails at once."""
    print("\nSending multiple invitation emails...")
    
    invites = [
        {
            "email": "user1@example.com",
            "first_name": "User",
            "invite_url": "https://yourapp.com/invite/user1",
            "inviter_name": "Team Admin"
        },
        {
            "email": "user2@example.com",
            "first_name": "Another",
            "invite_url": "https://yourapp.com/invite/user2",
            "inviter_name": "Team Admin"
        }
    ]
    
    results = await send_bulk_invites(
        invites=invites,
        app_name="Your Amazing App",
        expiry_days=7
    )
    
    print(f"Sent {len(results)} invitation emails")
    for i, result in enumerate(results):
        if "error" in result:
            print(f"Error sending to {invites[i]['email']}: {result['error']}")
        else:
            print(f"Successfully sent to {invites[i]['email']}")

async def main():
    """Run both examples."""
    await send_single_invite()
    await send_multiple_invites()

if __name__ == "__main__":
    asyncio.run(main())
