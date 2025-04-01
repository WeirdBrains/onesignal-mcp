import os
import json
import requests
import logging
from typing import List, Dict, Any, Optional, Union
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv

# Version information
__version__ = "1.0.0"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("onesignal-mcp")

# Load environment variables from .env file
load_dotenv()
logger.info("Environment variables loaded")

# Initialize the MCP server
mcp = FastMCP("onesignal-server")
logger.info("OneSignal MCP server initialized")

# OneSignal API configuration
ONESIGNAL_API_URL = "https://api.onesignal.com/api/v1"
ONESIGNAL_ORG_API_KEY = os.getenv("ONESIGNAL_ORG_API_KEY", "")

# Class to manage app configurations
class AppConfig:
    def __init__(self, app_id: str, api_key: str, name: str = None):
        self.app_id = app_id
        self.api_key = api_key
        self.name = name or app_id

    def __str__(self):
        return f"{self.name} ({self.app_id})"

# Dictionary to store app configurations
app_configs: Dict[str, AppConfig] = {}

# Load app configurations from environment variables
# Mandible app configuration
mandible_app_id = os.getenv("ONESIGNAL_MANDIBLE_APP_ID", "") or os.getenv("ONESIGNAL_APP_ID", "")
mandible_api_key = os.getenv("ONESIGNAL_MANDIBLE_API_KEY", "") or os.getenv("ONESIGNAL_API_KEY", "")
if mandible_app_id and mandible_api_key:
    app_configs["mandible"] = AppConfig(mandible_app_id, mandible_api_key, "Mandible")
    current_app_key = "mandible"
    logger.info(f"Mandible app configured with ID: {mandible_app_id}")

# Weird Brains app configuration
weirdbrains_app_id = os.getenv("ONESIGNAL_WEIRDBRAINS_APP_ID", "")
weirdbrains_api_key = os.getenv("ONESIGNAL_WEIRDBRAINS_API_KEY", "")
if weirdbrains_app_id and weirdbrains_api_key:
    app_configs["weirdbrains"] = AppConfig(weirdbrains_app_id, weirdbrains_api_key, "Weird Brains")
    if not current_app_key:
        current_app_key = "weirdbrains"
    logger.info(f"Weird Brains app configured with ID: {weirdbrains_app_id}")

# Fallback for default app configuration
if not app_configs:
    default_app_id = os.getenv("ONESIGNAL_APP_ID", "")
    default_api_key = os.getenv("ONESIGNAL_API_KEY", "")
    if default_app_id and default_api_key:
        app_configs["default"] = AppConfig(default_app_id, default_api_key, "Default App")
        current_app_key = "default"
        logger.info(f"Default app configured with ID: {default_app_id}")
    else:
        current_app_key = None
        logger.warning("No app configurations found. Use add_app to add an app configuration.")

# Function to add a new app configuration
def add_app_config(key: str, app_id: str, api_key: str, name: str = None) -> None:
    """Add a new app configuration to the available apps.
    
    Args:
        key: Unique identifier for this app configuration
        app_id: OneSignal App ID
        api_key: OneSignal REST API Key
        name: Display name for the app (optional)
    """
    app_configs[key] = AppConfig(app_id, api_key, name or key)
    logger.info(f"Added app configuration '{key}' with ID: {app_id}")

# Function to switch the current app
def set_current_app(app_key: str) -> bool:
    """Set the current app to use for API requests.
    
    Args:
        app_key: The key of the app configuration to use
        
    Returns:
        True if successful, False if the app key doesn't exist
    """
    global current_app_key
    if app_key in app_configs:
        current_app_key = app_key
        logger.info(f"Switched to app '{app_key}'")
        return True
    logger.error(f"Failed to switch app: '{app_key}' not found")
    return False

# Function to get the current app configuration
def get_current_app() -> Optional[AppConfig]:
    """Get the current app configuration.
    
    Returns:
        The current AppConfig or None if no app is set
    """
    if current_app_key and current_app_key in app_configs:
        return app_configs[current_app_key]
    return None

# Helper function to determine whether to use Organization API Key
def requires_org_api_key(endpoint: str) -> bool:
    """Determine if an endpoint requires the Organization API Key instead of a REST API Key.
    
    Args:
        endpoint: The API endpoint path
        
    Returns:
        True if the endpoint requires Organization API Key, False otherwise
    """
    # Organization-level endpoints that require Organization API Key
    org_level_endpoints = [
        "apps",                    # Managing apps
        "players/csv_export",      # Export users
        "notifications/csv_export"  # Export notifications
    ]
    
    # Check if endpoint starts with or matches any org-level endpoint
    for org_endpoint in org_level_endpoints:
        if endpoint == org_endpoint or endpoint.startswith(f"{org_endpoint}/"):
            return True
    
    return False

# Helper function for OneSignal API requests
async def make_onesignal_request(
    endpoint: str, 
    method: str = "GET", 
    data: Dict[str, Any] = None, 
    params: Dict[str, Any] = None, 
    use_org_key: bool = None,
    app_key: str = None
) -> Dict[str, Any]:
    """Make a request to the OneSignal API with proper authentication.
    
    Args:
        endpoint: API endpoint path
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Request body for POST/PUT requests
        params: Query parameters for GET requests
        use_org_key: Whether to use the organization API key instead of the REST API key
                     If None, will be automatically determined based on the endpoint
        app_key: The key of the app configuration to use (uses current app if None)
        
    Returns:
        API response as dictionary
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    # If use_org_key is not explicitly specified, determine it based on the endpoint
    if use_org_key is None:
        use_org_key = requires_org_api_key(endpoint)
    
    # Determine which app configuration to use
    app_config = None
    if not use_org_key:
        if app_key and app_key in app_configs:
            app_config = app_configs[app_key]
        elif current_app_key and current_app_key in app_configs:
            app_config = app_configs[current_app_key]
        
        if not app_config:
            error_msg = "No app configuration available. Use set_current_app or specify app_key."
            logger.error(error_msg)
            return {"error": error_msg}
        
        headers["Authorization"] = f"Basic {app_config.api_key}"
    else:
        if not ONESIGNAL_ORG_API_KEY:
            error_msg = "Organization API Key not configured. Set the ONESIGNAL_ORG_API_KEY environment variable."
            logger.error(error_msg)
            return {"error": error_msg}
        headers["Authorization"] = f"Basic {ONESIGNAL_ORG_API_KEY}"
    
    url = f"{ONESIGNAL_API_URL}/{endpoint}"
    
    # If using app-specific endpoint and not using org key, add app_id to params if not already present
    if not use_org_key and app_config:
        if params is None:
            params = {}
        if "app_id" not in params and not endpoint.startswith("apps/"):
            params["app_id"] = app_config.app_id
        
        # For POST/PUT requests, add app_id to data if not already present
        if data is not None and method in ["POST", "PUT"] and "app_id" not in data and not endpoint.startswith("apps/"):
            data["app_id"] = app_config.app_id
    
    try:
        logger.debug(f"Making {method} request to {url}")
        logger.debug(f"Using {'Organization API Key' if use_org_key else 'App REST API Key'}")
        if method == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=data, timeout=30)
        else:
            error_msg = f"Unsupported HTTP method: {method}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        response.raise_for_status()
        return response.json() if response.text else {}
    except requests.exceptions.RequestException as e:
        error_message = f"Error: {str(e)}"
        try:
            if hasattr(e, 'response') and e.response is not None:
                error_data = e.response.json()
                if isinstance(error_data, dict):
                    error_message = f"Error: {error_data.get('errors', [e.response.reason])[0]}"
        except Exception:
            pass
        logger.error(f"API request failed: {error_message}")
        return {"error": error_message}
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        logger.exception(error_message)
        return {"error": error_message}

# Resource for OneSignal configuration information
@mcp.resource("onesignal://config")
def get_onesignal_config() -> str:
    """Get information about the OneSignal configuration"""
    current_app = get_current_app()
    
    app_list = "\n".join([f"- {key}: {app}" for key, app in app_configs.items()])
    
    return f"""
    OneSignal Server Configuration:
    Version: {__version__}
    API URL: {ONESIGNAL_API_URL}
    Organization API Key Status: {'Configured' if ONESIGNAL_ORG_API_KEY else 'Not configured'}
    
    Available Apps:
    {app_list or "No apps configured"}
    
    Current App: {current_app.name if current_app else 'None'}
    
    This MCP server provides tools for:
    - Viewing and managing messages (push notifications, emails, SMS)
    - Viewing and managing user devices
    - Viewing and managing segments
    - Creating and managing templates
    - Viewing app information
    - Managing multiple OneSignal applications
    
    Make sure you have set the appropriate environment variables in your .env file.
    """

# === App Management Tools ===

@mcp.tool()
async def list_apps() -> str:
    """List all configured OneSignal apps in this server."""
    if not app_configs:
        return "No apps configured. Use add_app to add a new app configuration."
    
    current_app = get_current_app()
    
    result = ["Configured OneSignal Apps:"]
    for key, app in app_configs.items():
        current_marker = " (current)" if current_app and key == current_app_key else ""
        result.append(f"- {key}: {app.name} (App ID: {app.app_id}){current_marker}")
    
    return "\n".join(result)

@mcp.tool()
async def add_app(key: str, app_id: str, api_key: str, name: str = None) -> str:
    """Add a new OneSignal app configuration.
    
    Args:
        key: Unique identifier for this app configuration
        app_id: OneSignal App ID
        api_key: OneSignal REST API Key
        name: Display name for the app (optional)
    """
    if not key or not app_id or not api_key:
        return "Error: All parameters (key, app_id, api_key) are required."
        
    if key in app_configs:
        return f"Error: App key '{key}' already exists. Use a different key or update_app to modify it."
    
    add_app_config(key, app_id, api_key, name)
    
    # If this is the first app, set it as current
    global current_app_key
    if len(app_configs) == 1:
        current_app_key = key
    
    return f"Successfully added app '{key}' with name '{name or key}'."

@mcp.tool()
async def update_app(key: str, app_id: str = None, api_key: str = None, name: str = None) -> str:
    """Update an existing OneSignal app configuration.
    
    Args:
        key: The key of the app configuration to update
        app_id: New OneSignal App ID (optional)
        api_key: New OneSignal REST API Key (optional)
        name: New display name for the app (optional)
    """
    if key not in app_configs:
        return f"Error: App key '{key}' not found."
    
    app = app_configs[key]
    updated = []
    
    if app_id:
        app.app_id = app_id
        updated.append("App ID")
    if api_key:
        app.api_key = api_key
        updated.append("API Key")
    if name:
        app.name = name
        updated.append("Name")
    
    if not updated:
        return "No changes were made. Specify at least one parameter to update."
    
    logger.info(f"Updated app '{key}': {', '.join(updated)}")
    return f"Successfully updated app '{key}': {', '.join(updated)}."

@mcp.tool()
async def remove_app(key: str) -> str:
    """Remove an OneSignal app configuration.
    
    Args:
        key: The key of the app configuration to remove
    """
    if key not in app_configs:
        return f"Error: App key '{key}' not found."
    
    global current_app_key
    if current_app_key == key:
        if len(app_configs) > 1:
            # Set current to another app
            other_keys = [k for k in app_configs.keys() if k != key]
            current_app_key = other_keys[0]
            logger.info(f"Current app changed to '{current_app_key}' after removing '{key}'")
        else:
            current_app_key = None
            logger.warning("No current app set after removing the only app configuration")
    
    del app_configs[key]
    logger.info(f"Removed app configuration '{key}'")
    
    return f"Successfully removed app '{key}'."

@mcp.tool()
async def switch_app(key: str) -> str:
    """Switch the current app to use for API requests.
    
    Args:
        key: The key of the app configuration to use
    """
    if key not in app_configs:
        return f"Error: App key '{key}' not found. Available apps: {', '.join(app_configs.keys()) or 'None'}"
    
    global current_app_key
    current_app_key = key
    app = app_configs[key]
    
    return f"Switched to app '{key}' ({app.name})."

# === Message Management Tools ===

@mcp.tool()
async def send_notification(title: str, message: str, segment: str = "Subscribed Users", target_channel: str = "push", data: Dict[str, Any] = None):
    """Send a new push notification through OneSignal.
    
    Args:
        title: Notification title
        message: Notification message content
        segment: Target audience segment (default: "Subscribed Users")
        target_channel: Channel type (push, email, sms) (default: "push")
        data: Additional data to include with the notification (optional)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    notification_data = {
        "app_id": app_config.app_id,
        "target_channel": target_channel,
        "included_segments": [segment],
        "contents": {"en": message},
        "headings": {"en": title}
    }
    
    if data:
        notification_data["data"] = data
    
    # This endpoint uses app-specific REST API Key
    result = await make_onesignal_request("notifications", method="POST", data=notification_data, use_org_key=False)
    
    return result

@mcp.tool()
async def view_messages(limit: int = 20, offset: int = 0) -> str:
    """View recent messages sent through OneSignal.
    
    Args:
        limit: Maximum number of messages to return (default: 20, max: 50)
        offset: Result offset for pagination (default: 0)
    """
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    params = {"limit": min(limit, 50), "offset": offset}
    
    # This endpoint uses app-specific REST API Key
    result = await make_onesignal_request("notifications", method="GET", params=params, use_org_key=False)
    
    if "error" in result:
        return f"Error retrieving messages: {result['error']}"
    
    notifications = result.get("notifications", [])
    if not notifications:
        return "No messages found."
    
    output = "Messages:\n\n"
    
    for notification in notifications:
        output += f"ID: {notification.get('id')}\n"
        output += f"Title: {notification.get('headings', {}).get('en', 'No Title')}\n"
        output += f"Message: {notification.get('contents', {}).get('en', 'No Content')}\n"
        output += f"Created: {notification.get('created_at')}\n"
        output += f"Sent: {notification.get('sent_at')}\n"
        output += f"Status: {notification.get('completed_at', 'Pending')}\n"
        output += f"Successful: {notification.get('successful', 0)}\n"
        output += f"Failed: {notification.get('failed', 0)}\n"
        output += f"Remaining: {notification.get('remaining', 0)}\n\n"
    
    return output

@mcp.tool()
async def view_message_details(message_id: str) -> str:
    """Get detailed information about a specific message.
    
    Args:
        message_id: The ID of the message to retrieve details for
    """
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    # This endpoint uses app-specific REST API Key
    result = await make_onesignal_request(f"notifications/{message_id}", method="GET", use_org_key=False)
    
    if "error" in result:
        return f"Error retrieving message details: {result['error']}"
    
    output = f"ID: {result.get('id')}\n"
    output += f"App ID: {result.get('app_id')}\n"
    output += f"Title: {result.get('headings', {}).get('en', 'No Title')}\n"
    output += f"Message: {result.get('contents', {}).get('en', 'No Content')}\n"
    output += f"URL: {result.get('url')}\n"
    output += f"Created: {result.get('created_at')}\n"
    output += f"Sent: {result.get('sent_at')}\n"
    output += f"Completed: {result.get('completed_at')}\n"
    output += f"Successful: {result.get('successful')}\n"
    output += f"Failed: {result.get('failed')}\n"
    output += f"Remaining: {result.get('remaining')}\n"
    output += f"Platform Delivery Stats: {result.get('platform_delivery_stats')}\n"
    
    return output

@mcp.tool()
async def cancel_message(message_id: str) -> str:
    """Cancel a scheduled message that hasn't been delivered yet.
    
    Args:
        message_id: The ID of the message to cancel
    """
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    # This endpoint uses app-specific REST API Key
    result = await make_onesignal_request(f"notifications/{message_id}", method="DELETE", use_org_key=False)
    
    if "error" in result:
        return f"Error canceling message: {result['error']}"
    
    return "Message canceled successfully."

# === Device Management Tools ===

@mcp.tool()
async def view_devices(limit: int = 20, offset: int = 0) -> str:
    """View devices subscribed to your OneSignal app.
    
    Args:
        limit: Maximum number of devices to return (default: 20, max: 200)
        offset: Result offset for pagination (default: 0)
    """
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    params = {
        "app_id": app_config.app_id, 
        "limit": min(limit, 200), 
        "offset": offset
    }
    
    result = await make_onesignal_request("players", method="GET", params=params)
    
    if "error" in result:
        return f"Error fetching devices: {result['error']}"
    
    if not result.get("players"):
        return "No devices found."
    
    devices_info = []
    for device in result.get("players", []):
        devices_info.append(
            f"ID: {device.get('id')}\n"
            f"Device Type: {device.get('device_type')}\n"
            f"Created: {device.get('created_at')}\n"
            f"Last Active: {device.get('last_active')}\n"
            f"Session Count: {device.get('session_count')}\n"
            f"Platform: {device.get('device_os')}\n"
            f"Model: {device.get('device_model')}\n"
            f"Tags: {json.dumps(device.get('tags', {}), indent=2)}"
        )
    
    return "Devices:\n\n" + "\n\n".join(devices_info)

@mcp.tool()
async def view_device_details(device_id: str) -> str:
    """Get detailed information about a specific device.
    
    Args:
        device_id: The ID of the device to retrieve details for
    """
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    params = {"app_id": app_config.app_id}
    result = await make_onesignal_request(f"players/{device_id}", method="GET", params=params)
    
    if "error" in result:
        return f"Error fetching device details: {result['error']}"
    
    # Format the device details in a readable way
    details = [
        f"ID: {result.get('id')}",
        f"External User ID: {result.get('external_user_id', 'Not set')}",
        f"Device Type: {result.get('device_type')}",
        f"Device Model: {result.get('device_model')}",
        f"Platform: {result.get('device_os')}",
        f"Created: {result.get('created_at')}",
        f"Last Active: {result.get('last_active')}",
        f"Session Count: {result.get('session_count')}",
        f"Language: {result.get('language')}",
        f"Timezone: {result.get('timezone')}",
        f"Country: {result.get('country')}",
        f"Notification Types: {result.get('notification_types')}",
        f"Tags: {json.dumps(result.get('tags', {}), indent=2)}"
    ]
    
    return "\n".join(details)

# === Segment Management Tools ===

@mcp.tool()
async def view_segments() -> str:
    """List all segments available in your OneSignal app."""
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    # This endpoint uses app-specific REST API Key
    result = await make_onesignal_request("segments", method="GET", use_org_key=False)
    
    if "error" in result:
        return f"Error retrieving segments: {result['error']}"
    
    if not result:
        return "No segments found."
    
    output = "Segments:\n\n"
    
    for segment in result:
        output += f"ID: {segment.get('id')}\n"
        output += f"Name: {segment.get('name')}\n"
        output += f"Created: {segment.get('created_at')}\n"
        output += f"Updated: {segment.get('updated_at')}\n"
        output += f"Active: {segment.get('is_active', False)}\n"
        output += f"Read Only: {segment.get('read_only', False)}\n\n"
    
    return output

@mcp.tool()
async def create_segment(name: str, filters: str) -> str:
    """Create a new segment in your OneSignal app.
    
    Args:
        name: Name of the segment
        filters: JSON string representing the filters for this segment
               (e.g., '[{"field":"tag","key":"level","relation":"=","value":"10"}]')
    """
    try:
        parsed_filters = json.loads(filters)
    except json.JSONDecodeError:
        return "Error: The filters parameter must be a valid JSON string."
    
    data = {
        "name": name,
        "filters": parsed_filters
    }
    
    endpoint = f"apps/{get_current_app().app_id}/segments"
    result = await make_onesignal_request(endpoint, method="POST", data=data)
    
    if "error" in result:
        return f"Error creating segment: {result['error']}"
    
    return f"Segment '{name}' created successfully with ID: {result.get('id')}"

@mcp.tool()
async def delete_segment(segment_id: str) -> str:
    """Delete a segment from your OneSignal app.
    
    Args:
        segment_id: ID of the segment to delete
    """
    endpoint = f"apps/{get_current_app().app_id}/segments/{segment_id}"
    result = await make_onesignal_request(endpoint, method="DELETE")
    
    if "error" in result:
        return f"Error deleting segment: {result['error']}"
    
    return f"Segment '{segment_id}' deleted successfully"

# === Template Management Tools ===

@mcp.tool()
async def view_templates() -> str:
    """List all templates available in your OneSignal app."""
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    # This endpoint uses app-specific REST API Key
    result = await make_onesignal_request("templates", method="GET", use_org_key=False)
    
    if "error" in result:
        return f"Error retrieving templates: {result['error']}"
    
    templates = result.get("templates", [])
    
    if not templates:
        return "No templates found."
    
    output = "Templates:\n\n"
    
    for template in templates:
        output += f"ID: {template.get('id')}\n"
        output += f"Name: {template.get('name')}\n"
        output += f"Created: {template.get('created_at')}\n"
        output += f"Updated: {template.get('updated_at')}\n\n"
    
    return output

@mcp.tool()
async def view_template_details(template_id: str) -> str:
    """Get detailed information about a specific template.
    
    Args:
        template_id: The ID of the template to retrieve details for
    """
    params = {"app_id": get_current_app().app_id}
    result = await make_onesignal_request(f"templates/{template_id}", method="GET", params=params)
    
    if "error" in result:
        return f"Error fetching template details: {result['error']}"
    
    # Format the template details in a readable way
    heading = result.get("headings", {}).get("en", "No heading") if isinstance(result.get("headings"), dict) else "No heading"
    content = result.get("contents", {}).get("en", "No content") if isinstance(result.get("contents"), dict) else "No content"
    
    details = [
        f"ID: {result.get('id')}",
        f"Name: {result.get('name')}",
        f"Title: {heading}",
        f"Message: {content}",
        f"Platform: {result.get('platform')}",
        f"Created: {result.get('created_at')}"
    ]
    
    return "\n".join(details)

@mcp.tool()
async def create_template(name: str, title: str, message: str) -> str:
    """Create a new template in your OneSignal app.
    
    Args:
        name: Name of the template
        title: Title/heading of the template
        message: Content/message of the template
    """
    data = {
        "app_id": get_current_app().app_id,
        "name": name,
        "headings": {"en": title},
        "contents": {"en": message}
    }
    
    result = await make_onesignal_request("templates", method="POST", data=data)
    
    if "error" in result:
        return f"Error creating template: {result['error']}"
    
    return f"Template '{name}' created successfully with ID: {result.get('id')}"

# === App Information Tools ===

@mcp.tool()
async def view_app_details() -> str:
    """Get detailed information about the configured OneSignal app."""
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    # This endpoint requires the app_id in the URL and Organization API Key
    result = await make_onesignal_request(f"apps/{app_config.app_id}", method="GET", use_org_key=True)
    
    if "error" in result:
        return f"Error retrieving app details: {result['error']}"
    
    output = f"ID: {result.get('id')}\n"
    output += f"Name: {result.get('name')}\n"
    output += f"Created: {result.get('created_at')}\n"
    output += f"Updated: {result.get('updated_at')}\n"
    output += f"GCM: {'Configured' if result.get('gcm_key') else 'Not Configured'}\n"
    output += f"APNS: {'Configured' if result.get('apns_env') else 'Not Configured'}\n"
    output += f"Chrome: {'Configured' if result.get('chrome_web_key') else 'Not Configured'}\n"
    output += f"Safari: {'Configured' if result.get('safari_site_origin') else 'Not Configured'}\n"
    output += f"Email: {'Configured' if result.get('email_marketing') else 'Not Configured'}\n"
    output += f"SMS: {'Configured' if result.get('sms_marketing') else 'Not Configured'}\n"
    
    return output

@mcp.tool()
async def view_apps() -> str:
    """List all OneSignal applications for the organization (requires Organization API Key)."""
    result = await make_onesignal_request("apps", method="GET", use_org_key=True)
    
    if "error" in result:
        if "401" in str(result["error"]) or "403" in str(result["error"]):
            return ("Error: Your Organization API Key is either not configured or doesn't have permission to view all apps. "
                   "Make sure you've set the ONESIGNAL_ORG_API_KEY environment variable with a valid Organization API Key. "
                   "Organization API Keys can be found in your OneSignal dashboard under Organizations > Keys & IDs.")
        return f"Error fetching applications: {result['error']}"
    
    if not result:
        return "No applications found."
    
    apps_info = []
    for app in result:
        apps_info.append(
            f"ID: {app.get('id')}\n"
            f"Name: {app.get('name')}\n"
            f"GCM: {'Configured' if app.get('gcm_key') else 'Not Configured'}\n"
            f"APNS: {'Configured' if app.get('apns_env') else 'Not Configured'}\n"
            f"Created: {app.get('created_at')}"
        )
    
    return "Applications:\n\n" + "\n\n".join(apps_info)

# === Organization-level Tools ===

@mcp.tool()
async def create_app(name: str, site_name: str = None) -> str:
    """Create a new OneSignal application at the organization level (requires Organization API Key).
    
    Args:
        name: Name of the new application
        site_name: Optional name of the website for the application
    """
    data = {
        "name": name
    }
    
    if site_name:
        data["site_name"] = site_name
    
    result = await make_onesignal_request("apps", method="POST", data=data, use_org_key=True)
    
    if "error" in result:
        if "401" in str(result["error"]) or "403" in str(result["error"]):
            return ("Error: Your Organization API Key is either not configured or doesn't have permission to create apps. "
                   "Make sure you've set the ONESIGNAL_ORG_API_KEY environment variable with a valid Organization API Key.")
        return f"Error creating application: {result['error']}"
    
    return f"Application '{name}' created successfully with ID: {result.get('id')}"

@mcp.tool()
async def update_app(app_id: str, name: str = None, site_name: str = None) -> str:
    """Update an existing OneSignal application at the organization level (requires Organization API Key).
    
    Args:
        app_id: ID of the app to update
        name: New name for the application (optional)
        site_name: New site name for the application (optional)
    """
    data = {}
    
    if name:
        data["name"] = name
    
    if site_name:
        data["site_name"] = site_name
    
    if not data:
        return "Error: No update parameters provided. Specify at least one parameter to update."
    
    result = await make_onesignal_request(f"apps/{app_id}", method="PUT", data=data, use_org_key=True)
    
    if "error" in result:
        if "401" in str(result["error"]) or "403" in str(result["error"]):
            return ("Error: Your Organization API Key is either not configured or doesn't have permission to update apps. "
                   "Make sure you've set the ONESIGNAL_ORG_API_KEY environment variable with a valid Organization API Key.")
        return f"Error updating application: {result['error']}"
    
    return f"Application '{app_id}' updated successfully"

@mcp.tool()
async def view_app_api_keys(app_id: str) -> str:
    """View API keys for a specific OneSignal app (requires Organization API Key).
    
    Args:
        app_id: The ID of the app to retrieve API keys for
    """
    result = await make_onesignal_request(f"apps/{app_id}/auth/tokens", use_org_key=True)
    
    if "error" in result:
        if "401" in str(result["error"]) or "403" in str(result["error"]):
            return ("Error: Your Organization API Key is either not configured or doesn't have permission to view API keys. "
                   "Make sure you've set the ONESIGNAL_ORG_API_KEY environment variable with a valid Organization API Key.")
        return f"Error fetching API keys: {result['error']}"
    
    if not result.get("tokens", []):
        return f"No API keys found for app ID: {app_id}"
    
    keys_info = []
    for key in result.get("tokens", []):
        keys_info.append(
            f"ID: {key.get('id')}\n"
            f"Name: {key.get('name')}\n"
            f"Created: {key.get('created_at')}\n"
            f"Updated: {key.get('updated_at')}\n"
            f"IP Allowlist Mode: {key.get('ip_allowlist_mode', 'disabled')}"
        )
    
    return f"API Keys for App {app_id}:\n\n" + "\n\n".join(keys_info)

@mcp.tool()
async def create_app_api_key(app_id: str, name: str) -> str:
    """Create a new API key for a specific OneSignal app (requires Organization API Key).
    
    Args:
        app_id: The ID of the app to create an API key for
        name: Name for the new API key
    """
    data = {
        "name": name
    }
    
    result = await make_onesignal_request(f"apps/{app_id}/auth/tokens", method="POST", data=data, use_org_key=True)
    
    if "error" in result:
        if "401" in str(result["error"]) or "403" in str(result["error"]):
            return ("Error: Your Organization API Key is either not configured or doesn't have permission to create API keys. "
                   "Make sure you've set the ONESIGNAL_ORG_API_KEY environment variable with a valid Organization API Key.")
        return f"Error creating API key: {result['error']}"
    
    # Format the API key details for display
    key_details = (
        f"API Key '{name}' created successfully!\n\n"
        f"Key ID: {result.get('id')}\n"
        f"Token: {result.get('token')}\n\n"
        f"IMPORTANT: Save this token now! You won't be able to see the full token again."
    )
    
    return key_details

# Run the server
if __name__ == "__main__":
    # Run the server
    mcp.run()