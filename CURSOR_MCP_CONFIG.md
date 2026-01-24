# Cursor MCP Configuration Guide

## MCP Server Connection Method

This OneSignal MCP server runs in **stdio mode**, so you need to add the command to the Cursor configuration file.

## Configuration File Location

The Cursor MCP configuration file is located at:
- **macOS**: `~/Library/Application Support/Cursor/User/globalStorage/mcp.json`
- Or add it directly from Cursor settings

## Configuration Example

Add the following to your Cursor MCP configuration file (`mcp.json`):

```json
{
  "mcpServers": {
    "onesignal": {
      "command": "/Users/sunwoo/project/onesignal-mcp/venv/bin/python",
      "args": [
        "/Users/sunwoo/project/onesignal-mcp/onesignal_server.py"
      ],
      "env": {
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Or to use a relative path:

```json
{
  "mcpServers": {
    "onesignal": {
      "command": "python",
      "args": [
        "/Users/sunwoo/project/onesignal-mcp/onesignal_server.py"
      ],
      "cwd": "/Users/sunwoo/project/onesignal-mcp",
      "env": {
        "LOG_LEVEL": "INFO",
        "VIRTUAL_ENV": "/Users/sunwoo/project/onesignal-mcp/venv"
      }
    }
  }
}
```

## .env File Configuration

To use the OneSignal API, create a `.env` file in the project root:

```env
ONESIGNAL_APP_ID=your_app_id
ONESIGNAL_API_KEY=your_api_key
ONESIGNAL_ORG_API_KEY=your_org_api_key  # Optional
LOG_LEVEL=INFO
```

## Running in HTTP/SSE Mode (Optional)

To run as an HTTP server, modify the code or run as follows:

```python
# Modify the end of onesignal_server.py
if __name__ == "__main__":
    mcp.run(transport="sse")  # or "streamable-http"
```

Then it will be accessible at `http://localhost:8000`.

## Verification Method

1. Restart Cursor
2. Check if the MCP server is connected in Cursor
3. Verify that OneSignal-related tools are available



