#!/usr/bin/env python
"""
Example script demonstrating how to send a notification using the OneSignal MCP server.
"""
import asyncio
import sys
import os

# Add the parent directory to the path so we can import the server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the server module
from onesignal_server import send_notification

async def main():
    """Send a test notification to all subscribed users."""
    print("Sending a test notification...")
    
    result = await send_notification(
        title="Hello from OneSignal MCP",
        message="This is a test notification sent from the example script.",
        segment="Subscribed Users",
        data={"custom_key": "custom_value"}
    )
    
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Success! Notification ID: {result.get('id')}")
        print(f"Recipients: {result.get('recipients')}")

if __name__ == "__main__":
    asyncio.run(main())
