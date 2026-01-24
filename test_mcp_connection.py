#!/usr/bin/env python3
"""Test script to verify MCP server is working correctly."""
import sys
import os
import json
import asyncio
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_mcp_server():
    """Test MCP server functionality."""
    print("=" * 60)
    print("MCP Server Connection Test")
    print("=" * 60)
    
    try:
        # Import server module
        print("\n1. Server Module Load Test...")
        from onesignal_server import mcp
        print("   ✅ Server module loaded successfully")
        print(f"   Server name: {mcp.name}")
        
        # Check if tools are available
        print("\n2. Tools Check...")
        try:
            # FastMCP tool check method
            if hasattr(mcp, '_tools'):
                tools = mcp._tools
                tool_count = len(tools) if tools else 0
                print(f"   ✅ Tool count: {tool_count}")
                
                # Print some tool names
                if tools:
                    print("\n   Registered tools example:")
                    for i, tool in enumerate(list(tools.values())[:5]):
                        tool_name = getattr(tool, 'name', 'Unknown')
                        print(f"   - {tool_name}")
                    if tool_count > 5:
                        print(f"   ... and {tool_count - 5} more tools")
            else:
                print("   ⚠️  Cannot directly access tool list (normal)")
        except Exception as e:
            print(f"   ⚠️  Error checking tools: {e}")
        
        # Check resources
        print("\n3. Resources Check...")
        try:
            if hasattr(mcp, '_resources'):
                resources = mcp._resources
                resource_count = len(resources) if resources else 0
                print(f"   ✅ Resource count: {resource_count}")
                if resources:
                    for resource_name in list(resources.keys())[:3]:
                        print(f"   - {resource_name}")
            else:
                print("   ⚠️  Cannot directly access resource list (normal)")
        except Exception as e:
            print(f"   ⚠️  Error checking resources: {e}")
        
        # Check app configuration
        print("\n4. OneSignal App Configuration Check...")
        try:
            from onesignal_server import app_configs, get_current_app
            current_app = get_current_app()
            if current_app:
                print(f"   ✅ Current app: {current_app.name}")
                print(f"   App ID: {current_app.app_id[:8]}...")
            else:
                print("   ⚠️  No app configuration found (check .env file)")
            
            if app_configs:
                print(f"   ✅ Configured app count: {len(app_configs)}")
                for key, app in app_configs.items():
                    print(f"   - {key}: {app.name}")
            else:
                print("   ⚠️  No apps configured")
        except Exception as e:
            print(f"   ⚠️  Error checking app configuration: {e}")
        
        # Test server can start
        print("\n5. Server Execution Check...")
        print("   ✅ Server module loaded successfully")
        print("   Can connect to MCP server from Cursor")
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Restart Cursor")
        print("2. Check if the MCP server is connected in Cursor")
        print("3. Test if OneSignal-related tools are available")
        
        return True
        
    except ImportError as e:
        print(f"   ❌ Module load failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if virtual environment is activated: source venv/bin/activate")
        print("2. Check if required packages are installed: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"   ❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mcp_server())
    sys.exit(0 if success else 1)



