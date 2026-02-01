import os
import json
import base64
import requests
import logging
from typing import List, Dict, Any, Optional, Union
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv

# Server information
__version__ = "2.1.0"

# Configure logging
logging.basicConfig(
    level=logging.INFO, # Default level, will be overridden by env var if set
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("onesignal-mcp")

# Load environment variables from .env file
load_dotenv()
logger.info("Environment variables loaded")

# Get log level from environment, default to INFO, and ensure it's uppercase
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if log_level_str not in valid_log_levels:
    logger.warning(f"Invalid LOG_LEVEL '{log_level_str}' found in environment. Using INFO instead.")
    log_level_str = "INFO"

# Apply the validated log level
logger.setLevel(log_level_str)

# Initialize the MCP server, passing the validated log level
mcp = FastMCP("onesignal-server", log_level=log_level_str)
logger.info(f"OneSignal MCP server initialized with log level: {log_level_str}")

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
    logger.warning("No current app is set. Use switch_app(key) to select an app.")
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
        "notifications/csv_export",  # Export notifications
        "players/csv_export"        # Export players/subscriptions
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
    app_key: str = None,
    headers: Dict[str, str] = None
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
        headers: Additional headers to include in the request (optional)
        
    Returns:
        API response as dictionary
    """
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    # Merge additional headers if provided
    if headers:
        request_headers.update(headers)
    
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
        
        # Check if it's a v2 API key
        if app_config.api_key.startswith("os_v2_"):
            request_headers["Authorization"] = f"Key {app_config.api_key}"
        else:
            # Basic auth requires base64 encoding of "api_key:"
            encoded_key = base64.b64encode(f"{app_config.api_key}:".encode()).decode()
            request_headers["Authorization"] = f"Basic {encoded_key}"
    else:
        if not ONESIGNAL_ORG_API_KEY:
            error_msg = "Organization API Key not configured. Set the ONESIGNAL_ORG_API_KEY environment variable."
            logger.error(error_msg)
            return {"error": error_msg}
        # Check if it's a v2 API key
        if ONESIGNAL_ORG_API_KEY.startswith("os_v2_"):
            request_headers["Authorization"] = f"Key {ONESIGNAL_ORG_API_KEY}"
        else:
            # Basic auth requires base64 encoding of "api_key:"
            encoded_key = base64.b64encode(f"{ONESIGNAL_ORG_API_KEY}:".encode()).decode()
            request_headers["Authorization"] = f"Basic {encoded_key}"
    
    url = f"{ONESIGNAL_API_URL}/{endpoint}"
    
    # If using app-specific endpoint and not using org key, add app_id to params if not already present
    if not use_org_key and app_config:
        if params is None:
            params = {}
        # For GET and DELETE requests, add app_id to query parameters
        if "app_id" not in params and not endpoint.startswith("apps/") and method in ["GET", "DELETE"]:
            params["app_id"] = app_config.app_id
        
        # For POST/PUT/PATCH requests, add app_id to data if not already present
        if data is not None and method in ["POST", "PUT", "PATCH"] and "app_id" not in data and not endpoint.startswith("apps/"):
            data["app_id"] = app_config.app_id
    
    try:
        logger.debug(f"Making {method} request to {url}")
        logger.debug(f"Using {'Organization API Key' if use_org_key else 'App REST API Key'}")
        logger.debug(f"Authorization header type: {request_headers['Authorization'].split(' ')[0]}")
        if method == "GET":
            response = requests.get(url, headers=request_headers, params=params, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=request_headers, json=data, timeout=30)
        elif method == "PUT":
            response = requests.put(url, headers=request_headers, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, headers=request_headers, params=params, timeout=30)
        elif method == "PATCH":
            response = requests.patch(url, headers=request_headers, json=data, timeout=30)
        else:
            error_msg = f"Unsupported HTTP method: {method}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Handle 404 responses gracefully
        if response.status_code == 404:
            # For some endpoints, 404 means "no data" not an error
            if endpoint.endswith("/templates") or "templates" in endpoint:
                return {"templates": [], "message": "No templates found"}
            # Return empty result for other 404s
            return {"error": "Resource not found", "status_code": 404}
        
        response.raise_for_status()
        return response.json() if response.text else {}
    except requests.exceptions.HTTPError as e:
        error_message = f"Error: {str(e)}"
        status_code = None
        try:
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                error_data = e.response.json()
                if isinstance(error_data, dict):
                    errors = error_data.get('errors', [])
                    if errors:
                        if isinstance(errors, list):
                            error_message = f"Error: {errors[0]}"
                        else:
                            error_message = f"Error: {errors}"
                    elif 'error' in error_data:
                        error_message = f"Error: {error_data['error']}"
                    elif 'message' in error_data:
                        error_message = f"Error: {error_data['message']}"
                    else:
                        error_message = f"Error: {e.response.reason}"
        except Exception:
            pass
        
        # Provide more context for authorization errors
        if status_code == 401 or status_code == 403:
            auth_type = "Organization API Key" if use_org_key else "App REST API Key"
            error_message = (
                f"Authorization failed ({auth_type}). "
                f"Status: {status_code}. "
                f"Details: {error_message}. "
                f"Endpoint: {endpoint}"
            )
        
        logger.error(f"API request failed: {error_message}")
        return {"error": error_message, "status_code": status_code}
    except requests.exceptions.RequestException as e:
        error_message = f"Request failed: {str(e)}"
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
    - Managing users and subscriptions
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
    """Add a new OneSignal app configuration locally.
    
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
async def update_local_app_config(key: str, app_id: str = None, api_key: str = None, name: str = None) -> str:
    """Update an existing local OneSignal app configuration.
    
    Args:
        key: The key of the app configuration to update locally
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
    """Remove a local OneSignal app configuration.
    
    Args:
        key: The key of the app configuration to remove locally
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
async def send_push_notification(title: str, message: str, segments: List[str] = None, external_ids: List[str] = None, data: Dict[str, Any] = None, idempotency_key: str = None) -> Dict[str, Any]:
    """Send a new push notification through OneSignal.
    
    Args:
        title: Notification title.
        message: Notification message content.
        segments: List of segments to include (e.g., ["Subscribed Users"]).
        external_ids: List of external user IDs to target.
        data: Additional data to include with the notification (optional).
        idempotency_key: Optional idempotency key to prevent duplicate messages (up to 64 alphanumeric characters).
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    if not segments and not external_ids:
        segments = ["Subscribed Users"] # Default if no target specified
    
    notification_data = {
        "app_id": app_config.app_id,
        "contents": {"en": message},
        "headings": {"en": title},
        "target_channel": "push"
    }
    
    if segments:
        notification_data["included_segments"] = segments
    if external_ids:
        # Assuming make_onesignal_request handles converting list to JSON
        notification_data["include_external_user_ids"] = external_ids
    
    if data:
        notification_data["data"] = data
    
    # This endpoint uses app-specific REST API Key
    # Add idempotency_key to headers if provided
    extra_headers = {}
    if idempotency_key:
        extra_headers["Idempotency-Key"] = idempotency_key
    
    result = await make_onesignal_request("notifications", method="POST", data=notification_data, use_org_key=False, headers=extra_headers if extra_headers else None)
    
    return result

@mcp.tool()
async def view_messages(limit: int = 20, offset: int = 0, kind: int = None) -> Dict[str, Any]:
    """View recent messages sent through OneSignal.
    
    Args:
        limit: Maximum number of messages to return (default: 20, max: 50)
        offset: Result offset for pagination (default: 0)
        kind: Filter by message type (0=Dashboard, 1=API, 3=Automated) (optional)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    params = {"limit": min(limit, 50), "offset": offset}
    if kind is not None:
        params["kind"] = kind
    
    # This endpoint uses app-specific REST API Key
    result = await make_onesignal_request("notifications", method="GET", params=params, use_org_key=False)
    
    # Return the raw JSON result for flexibility
    return result

@mcp.tool()
async def view_message_details(message_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific message.
    
    Args:
        message_id: The ID of the message to retrieve details for
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # This endpoint uses app-specific REST API Key
    result = await make_onesignal_request(f"notifications/{message_id}", method="GET", use_org_key=False)
    
    # Return the raw JSON result
    return result

@mcp.tool()
async def view_message_history(message_id: str, event: str) -> Dict[str, Any]:
    """View the history / recipients of a message based on events.
    
    Args:
        message_id: The ID of the message.
        event: The event type to track (e.g., 'sent', 'clicked').
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    data = {
        "app_id": app_config.app_id,
        "events": event,
        "email": get_current_app().name + "-history@example.com" # Requires an email to send the CSV report
    }
    
    # Endpoint uses REST API Key
    result = await make_onesignal_request(f"notifications/{message_id}/history", method="POST", data=data, use_org_key=False)
    return result

@mcp.tool()
async def cancel_message(message_id: str) -> Dict[str, Any]:
    """Cancel a scheduled message that hasn't been delivered yet.
    
    Args:
        message_id: The ID of the message to cancel
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # This endpoint uses app-specific REST API Key
    result = await make_onesignal_request(f"notifications/{message_id}", method="DELETE", use_org_key=False)
    
    return result

# === Segment Management Tools ===

@mcp.tool()
async def view_segments() -> str:
    """List all segments available in your OneSignal app."""
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    # This endpoint requires app_id in the URL path
    endpoint = f"apps/{app_config.app_id}/segments"
    result = await make_onesignal_request(endpoint, method="GET", use_org_key=False)
    
    # Check if result is a dictionary with an error
    if isinstance(result, dict) and "error" in result:
        return f"Error retrieving segments: {result['error']}"
    
    # Handle different response formats
    if isinstance(result, dict):
        # Some endpoints return segments in a wrapper object
        segments = result.get("segments", [])
    elif isinstance(result, list):
        # Direct list of segments
        segments = result
    else:
        return f"Unexpected response format: {type(result)}"
    
    if not segments:
        return "No segments found."
    
    output = "Segments:\n\n"
    
    for segment in segments:
        if isinstance(segment, dict):
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
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    try:
        parsed_filters = json.loads(filters)
    except json.JSONDecodeError:
        return "Error: The filters parameter must be a valid JSON string."
    
    data = {
        "name": name,
        "filters": parsed_filters
    }
    
    endpoint = f"apps/{app_config.app_id}/segments"
    result = await make_onesignal_request(endpoint, method="POST", data=data, use_org_key=False)
    
    if "error" in result:
        return f"Error creating segment: {result['error']}"
    
    return f"Segment '{name}' created successfully with ID: {result.get('id')}"

@mcp.tool()
async def delete_segment(segment_id: str) -> str:
    """Delete a segment from your OneSignal app.
    
    Args:
        segment_id: ID of the segment to delete
    """
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    # Segments use apps/{app_id}/segments/{segment_id} format
    # app_id is already in the URL path, so no need for params
    endpoint = f"apps/{app_config.app_id}/segments/{segment_id}"
    result = await make_onesignal_request(endpoint, method="DELETE", use_org_key=False)
    
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
    
    # OneSignal API uses /templates endpoint with app_id as query parameter
    # The make_onesignal_request function will automatically add app_id to params
    # since the endpoint doesn't start with "apps/"
    endpoint = "templates"
    result = await make_onesignal_request(endpoint, method="GET", use_org_key=False)
    
    if "error" in result:
        # Check if it's a 404 (no templates)
        if result.get("status_code") == 404 or "not found" in result.get("error", "").lower():
            return "No templates found."
        return f"Error retrieving templates: {result['error']}"
    
    # Handle both direct array response and wrapped response
    if isinstance(result, list):
        templates = result
    else:
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
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    # OneSignal API uses GET /templates/{template_id} with app_id as query parameter
    # The make_onesignal_request function will automatically add app_id to params
    # since the endpoint doesn't start with "apps/"
    endpoint = f"templates/{template_id}"
    result = await make_onesignal_request(endpoint, method="GET", use_org_key=False)
    
    if "error" in result:
        return f"Error fetching template details: {result['error']}"
    
    # Helper function to extract text from headings/contents
    def extract_text(field_value, default="No value"):
        """Extract text from headings or contents field, handling various formats."""
        if field_value is None:
            return default
        
        if isinstance(field_value, str):
            return field_value.strip() if field_value.strip() else default
        
        if isinstance(field_value, dict):
            # Try common language keys in order of preference
            for lang_key in ["en", "en-US", "en_US", "default"]:
                if lang_key in field_value:
                    value = field_value[lang_key]
                    if value and isinstance(value, str) and value.strip():
                        return value.strip()
                    elif value:  # Non-string value
                        return str(value)
            
            # If no common key found, try first non-empty value
            for key, value in field_value.items():
                if value:
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                    elif value:
                        return str(value)
        
        return default
    
    # Handle headings - check both top-level and nested structures
    headings = result.get("headings") or result.get("content", {}).get("headings")
    heading = extract_text(headings, "No heading")
    
    # Handle contents - check both top-level and nested structures
    contents = result.get("contents") or result.get("content", {}).get("contents")
    content = extract_text(contents, "No content")
    
    details = [
        f"ID: {result.get('id', 'N/A')}",
        f"Name: {result.get('name', 'N/A')}",
        f"Title: {heading}",
        f"Message: {content}",
    ]
    
    # Add optional fields if present
    if result.get('platform'):
        details.append(f"Platform: {result.get('platform')}")
    if result.get('created_at'):
        details.append(f"Created: {result.get('created_at')}")
    if result.get('updated_at'):
        details.append(f"Updated: {result.get('updated_at')}")
    if result.get('template_type'):
        details.append(f"Type: {result.get('template_type')}")
    
    return "\n".join(details)

@mcp.tool()
async def create_template(name: str, title: str, message: str) -> str:
    """Create a new template in your OneSignal app.
    
    Args:
        name: Name of the template
        title: Title/heading of the template
        message: Content/message of the template
    """
    app_config = get_current_app()
    if not app_config:
        return "No app currently selected. Use switch_app to select an app."
    
    # OneSignal API uses POST /templates endpoint with app_id in request body
    data = {
        "app_id": app_config.app_id,
        "name": name,
        "headings": {"en": title},
        "contents": {"en": message}
    }
    
    endpoint = "templates"
    result = await make_onesignal_request(endpoint, method="POST", data=data, use_org_key=False)
    
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
    result = await make_onesignal_request(f"apps/{app_id}/auth/tokens", method="GET", use_org_key=True)
    
    if "error" in result:
        status_code = result.get("status_code")
        if status_code == 401 or status_code == 403:
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

# === User Management Tools ===

@mcp.tool()
async def create_user(name: str = None, email: str = None, external_id: str = None, tags: Dict[str, str] = None) -> Dict[str, Any]:
    """Create a new user in OneSignal.
    
    Args:
        name: User's name (optional)
        email: User's email address (optional)
        external_id: External user ID for identification (optional)
        tags: Additional user tags/properties (optional)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id
    }
    if name:
        data["name"] = name
    if email:
        data["email"] = email
    if external_id:
        data["external_user_id"] = external_id
    if tags:
        data["tags"] = tags
    
    result = await make_onesignal_request("users", method="POST", data=data, use_org_key=False)
    return result

@mcp.tool()
async def view_user(user_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific user.
    
    Args:
        user_id: The OneSignal User ID to retrieve details for
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    result = await make_onesignal_request(f"users/{user_id}", method="GET", use_org_key=False)
    return result

@mcp.tool()
async def update_user(user_id: str, name: str = None, email: str = None, tags: Dict[str, str] = None) -> Dict[str, Any]:
    """Update an existing user's information.
    
    Args:
        user_id: The OneSignal User ID to update
        name: New name for the user (optional)
        email: New email address (optional)
        tags: New or updated tags/properties (optional)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id
    }
    if name:
        data["name"] = name
    if email:
        data["email"] = email
    if tags:
        data["tags"] = tags
    
    # Check if there are any update parameters besides app_id
    if len(data) == 1:  # Only app_id present
        return {"error": "No update parameters provided"}
    
    result = await make_onesignal_request(f"users/{user_id}", method="PATCH", data=data, use_org_key=False)
    return result

@mcp.tool()
async def delete_user(user_id: str) -> Dict[str, Any]:
    """Delete a user and all their subscriptions.
    
    Args:
        user_id: The OneSignal User ID to delete
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    result = await make_onesignal_request(f"users/{user_id}", method="DELETE", use_org_key=False)
    return result

@mcp.tool()
async def view_user_identity(user_id: str) -> Dict[str, Any]:
    """Get user identity information.
    
    Args:
        user_id: The OneSignal User ID to retrieve identity for
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    result = await make_onesignal_request(f"users/{user_id}/identity", method="GET", use_org_key=False)
    return result

@mcp.tool()
async def create_or_update_alias(user_id: str, alias_label: str, alias_id: str) -> Dict[str, Any]:
    """Create or update a user alias.
    
    Args:
        user_id: The OneSignal User ID
        alias_label: The type/label of the alias (e.g., "email", "phone", "external")
        alias_id: The alias identifier value
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id,
        "alias": {
            alias_label: alias_id
        }
    }
    
    result = await make_onesignal_request(f"users/{user_id}/identity", method="PATCH", data=data, use_org_key=False)
    return result

@mcp.tool()
async def delete_alias(user_id: str, alias_label: str) -> Dict[str, Any]:
    """Delete a user alias.
    
    Args:
        user_id: The OneSignal User ID
        alias_label: The type/label of the alias to delete
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    result = await make_onesignal_request(f"users/{user_id}/identity/{alias_label}", method="DELETE", use_org_key=False)
    return result

# === Subscription Management Tools ===

@mcp.tool()
async def create_subscription(user_id: str, subscription_type: str, identifier: str) -> Dict[str, Any]:
    """Create a new subscription for a user.
    
    Args:
        user_id: The OneSignal User ID
        subscription_type: Type of subscription ("email", "sms", "push")
        identifier: Email address or phone number for the subscription
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id,
        "subscription": {
            "type": subscription_type,
            "identifier": identifier
        }
    }
    
    result = await make_onesignal_request(f"users/{user_id}/subscriptions", method="POST", data=data, use_org_key=False)
    return result

@mcp.tool()
async def update_subscription(user_id: str, subscription_id: str, enabled: bool = None) -> Dict[str, Any]:
    """Update a user's subscription.
    
    Args:
        user_id: The OneSignal User ID
        subscription_id: The ID of the subscription to update
        enabled: Whether the subscription should be enabled or disabled (optional)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id
    }
    if enabled is not None:
        data["enabled"] = enabled
    
    result = await make_onesignal_request(f"users/{user_id}/subscriptions/{subscription_id}", method="PATCH", data=data, use_org_key=False)
    return result

@mcp.tool()
async def delete_subscription(user_id: str, subscription_id: str) -> Dict[str, Any]:
    """Delete a user's subscription.
    
    Args:
        user_id: The OneSignal User ID
        subscription_id: The ID of the subscription to delete
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    result = await make_onesignal_request(f"users/{user_id}/subscriptions/{subscription_id}", method="DELETE", use_org_key=False)
    return result

@mcp.tool()
async def transfer_subscription(user_id: str, subscription_id: str, new_user_id: str) -> Dict[str, Any]:
    """Transfer a subscription from one user to another.
    
    Args:
        user_id: The current OneSignal User ID
        subscription_id: The ID of the subscription to transfer
        new_user_id: The OneSignal User ID to transfer the subscription to
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id,
        "new_user_id": new_user_id
    }
    
    result = await make_onesignal_request(f"users/{user_id}/subscriptions/{subscription_id}/transfer", method="PATCH", data=data, use_org_key=False)
    return result

@mcp.tool()
async def unsubscribe_email(token: str) -> Dict[str, Any]:
    """Unsubscribe an email subscription using an unsubscribe token.
    
    Args:
        token: The unsubscribe token from the email
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    data = {
        "token": token
    }
    
    result = await make_onesignal_request("email/unsubscribe", method="POST", data=data, use_org_key=False)
    return result

@mcp.tool()
async def view_subscription_by_token(subscription_token: str) -> Dict[str, Any]:
    """View subscription details by subscription token.
    
    Args:
        subscription_token: The subscription token to retrieve details for
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    result = await make_onesignal_request(f"subscriptions/{subscription_token}", method="GET", use_org_key=False)
    return result

@mcp.tool()
async def update_subscription_by_token(subscription_token: str, enabled: bool = None) -> Dict[str, Any]:
    """Update a subscription by subscription token.
    
    Args:
        subscription_token: The subscription token to update
        enabled: Whether the subscription should be enabled or disabled (optional)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id
    }
    if enabled is not None:
        data["enabled"] = enabled
    
    # Check if there are any update parameters besides app_id
    if len(data) == 1:  # Only app_id present
        return {"error": "No update parameters provided"}
    
    result = await make_onesignal_request(f"subscriptions/{subscription_token}", method="PATCH", data=data, use_org_key=False)
    return result

@mcp.tool()
async def view_user_identity_by_subscription(subscription_id: str) -> Dict[str, Any]:
    """View user identity information by subscription ID.
    
    Args:
        subscription_id: The subscription ID to retrieve identity for
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    endpoint = f"apps/{app_config.app_id}/subscriptions/{subscription_id}/identity"
    result = await make_onesignal_request(endpoint, method="GET", use_org_key=False)
    return result

@mcp.tool()
async def create_alias_by_subscription(subscription_id: str, alias_label: str, alias_id: str) -> Dict[str, Any]:
    """Create or update a user alias by subscription ID.
    
    Args:
        subscription_id: The subscription ID
        alias_label: The type/label of the alias (e.g., "email", "phone", "external")
        alias_id: The alias identifier value
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    # Note: app_id is also in URL path, but including in body for consistency
    data = {
        "app_id": app_config.app_id,
        "alias": {
            alias_label: alias_id
        }
    }
    
    endpoint = f"apps/{app_config.app_id}/subscriptions/{subscription_id}/identity"
    result = await make_onesignal_request(endpoint, method="PATCH", data=data, use_org_key=False)
    return result

# === NEW: Email & SMS Messaging Tools ===

@mcp.tool()
async def send_email(subject: str, body: str, email_body: str = None, 
                     include_emails: List[str] = None, segments: List[str] = None,
                     external_ids: List[str] = None, template_id: str = None,
                     idempotency_key: str = None) -> Dict[str, Any]:
    """Send an email through OneSignal.
    
    Args:
        subject: Email subject line
        body: Plain text email content  
        email_body: HTML email content (optional)
        include_emails: List of specific email addresses to target
        segments: List of segments to include
        external_ids: List of external user IDs to target
        template_id: Email template ID to use
        idempotency_key: Optional idempotency key to prevent duplicate messages (up to 64 alphanumeric characters)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    email_data = {
        "app_id": app_config.app_id,
        "email_subject": subject,
        "email_body": email_body or body,
        "target_channel": "email"
    }
    
    # Set targeting
    if include_emails:
        email_data["include_emails"] = include_emails
    elif external_ids:
        email_data["include_external_user_ids"] = external_ids
    elif segments:
        email_data["included_segments"] = segments
    else:
        email_data["included_segments"] = ["Subscribed Users"]
    
    if template_id:
        email_data["template_id"] = template_id
    
    extra_headers = {}
    if idempotency_key:
        extra_headers["Idempotency-Key"] = idempotency_key
    
    result = await make_onesignal_request("notifications", method="POST", data=email_data, use_org_key=False, headers=extra_headers if extra_headers else None)
    return result

@mcp.tool()
async def send_sms(message: str, phone_numbers: List[str] = None, 
                   segments: List[str] = None, external_ids: List[str] = None,
                   media_url: str = None, idempotency_key: str = None) -> Dict[str, Any]:
    """Send an SMS/MMS through OneSignal.
    
    Args:
        message: SMS message content
        phone_numbers: List of phone numbers in E.164 format
        segments: List of segments to include
        external_ids: List of external user IDs to target
        media_url: URL for MMS media attachment
        idempotency_key: Optional idempotency key to prevent duplicate messages (up to 64 alphanumeric characters)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    sms_data = {
        "app_id": app_config.app_id,
        "contents": {"en": message},
        "target_channel": "sms"
    }
    
    if phone_numbers:
        sms_data["include_phone_numbers"] = phone_numbers
    elif external_ids:
        sms_data["include_external_user_ids"] = external_ids
    elif segments:
        sms_data["included_segments"] = segments
    else:
        return {"error": "SMS requires phone_numbers, external_ids, or segments"}
    
    if media_url:
        sms_data["mms_media_url"] = media_url
    
    extra_headers = {}
    if idempotency_key:
        extra_headers["Idempotency-Key"] = idempotency_key
    
    result = await make_onesignal_request("notifications", method="POST", data=sms_data, use_org_key=False, headers=extra_headers if extra_headers else None)
    return result

@mcp.tool()
async def send_transactional_message(channel: str, content: Dict[str, str], 
                                   recipients: Dict[str, Any], template_id: str = None,
                                   custom_data: Dict[str, Any] = None,
                                   idempotency_key: str = None) -> Dict[str, Any]:
    """Send a transactional message (immediate delivery, no scheduling).
    
    Args:
        channel: Channel to send on ("push", "email", "sms")
        content: Message content (format depends on channel)
        recipients: Targeting information (include_external_user_ids, include_emails, etc.)
        template_id: Template ID to use
        custom_data: Custom data to include
        idempotency_key: Optional idempotency key to prevent duplicate messages (up to 64 alphanumeric characters)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    message_data = {
        "app_id": app_config.app_id,
        "target_channel": channel,
        "is_transactional": True
    }
    
    # Set content based on channel
    if channel == "email":
        message_data["email_subject"] = content.get("subject", "")
        message_data["email_body"] = content.get("body", "")
    else:
        message_data["contents"] = content
    
    # Set recipients
    message_data.update(recipients)
    
    if template_id:
        message_data["template_id"] = template_id
    
    if custom_data:
        message_data["data"] = custom_data
    
    extra_headers = {}
    if idempotency_key:
        extra_headers["Idempotency-Key"] = idempotency_key
    
    result = await make_onesignal_request("notifications", method="POST", data=message_data, use_org_key=False, headers=extra_headers if extra_headers else None)
    return result

# === NEW: Enhanced Template Management ===

@mcp.tool()
async def update_template(template_id: str, name: str = None, 
                         title: str = None, message: str = None) -> Dict[str, Any]:
    """Update an existing template.
    
    Args:
        template_id: ID of the template to update
        name: New name for the template
        title: New title/heading for the template
        message: New content/message for the template
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    data = {
        "app_id": app_config.app_id
    }
    
    if name:
        data["name"] = name
    if title:
        data["headings"] = {"en": title}
    if message:
        data["contents"] = {"en": message}
    
    # Check if there are any update parameters besides app_id
    if len(data) == 1:  # Only app_id present
        return {"error": "No update parameters provided"}
    
    # OneSignal API uses PATCH /templates/{template_id} with app_id in request body
    endpoint = f"templates/{template_id}"
    result = await make_onesignal_request(endpoint, method="PATCH", data=data, use_org_key=False)
    
    return result

@mcp.tool()
async def delete_template(template_id: str) -> Dict[str, Any]:
    """Delete a template from your OneSignal app.
    
    Args:
        template_id: ID of the template to delete
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # OneSignal API uses DELETE /templates/{template_id} with app_id as query parameter
    # Explicitly add app_id to params to ensure it's included
    endpoint = f"templates/{template_id}"
    params = {"app_id": app_config.app_id}
    result = await make_onesignal_request(endpoint, method="DELETE", params=params, use_org_key=False)
    
    if "error" not in result:
        return {"success": f"Template '{template_id}' deleted successfully"}
    return result

@mcp.tool()
async def copy_template_to_app(template_id: str, target_app_id: str, 
                               new_name: str = None) -> Dict[str, Any]:
    """Copy a template to another OneSignal app.
    
    Args:
        template_id: ID of the template to copy
        target_app_id: ID of the app to copy the template to
        new_name: Optional new name for the copied template
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # OneSignal API uses POST /templates/{template_id}/copy
    # The target app_id is included in the request body
    data = {"app_id": target_app_id}
    
    if new_name:
        data["name"] = new_name
    
    endpoint = f"templates/{template_id}/copy"
    result = await make_onesignal_request(endpoint, method="POST", data=data, use_org_key=False)
    
    return result

# === NEW: Live Activities (iOS) ===

@mcp.tool()
async def start_live_activity(activity_id: str, push_token: str, 
                             subscription_id: str, activity_attributes: Dict[str, Any],
                             content_state: Dict[str, Any]) -> Dict[str, Any]:
    """Start a new iOS Live Activity.
    
    Args:
        activity_id: Unique identifier for the activity
        push_token: Push token for the Live Activity
        subscription_id: Subscription ID for the user
        activity_attributes: Static attributes for the activity
        content_state: Initial dynamic content state
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id,
        "activity_id": activity_id,
        "push_token": push_token,
        "subscription_id": subscription_id,
        "activity_attributes": activity_attributes,
        "content_state": content_state
    }
    
    result = await make_onesignal_request(f"live_activities/{activity_id}/start",
                                        method="POST", data=data, use_org_key=False)
    return result

@mcp.tool()
async def update_live_activity(activity_id: str, name: str, event: str,
                              content_state: Dict[str, Any], 
                              dismissal_date: int = None, priority: int = None,
                              sound: str = None) -> Dict[str, Any]:
    """Update an existing iOS Live Activity.
    
    Args:
        activity_id: ID of the activity to update
        name: Name identifier for the update
        event: Event type ("update" or "end")
        content_state: Updated dynamic content state
        dismissal_date: Unix timestamp for automatic dismissal
        priority: Notification priority (5-10)
        sound: Sound file name for the update
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id,
        "name": name,
        "event": event,
        "content_state": content_state
    }
    
    if dismissal_date:
        data["dismissal_date"] = dismissal_date
    if priority:
        data["priority"] = priority
    if sound:
        data["sound"] = sound
    
    result = await make_onesignal_request(f"live_activities/{activity_id}/update",
                                        method="POST", data=data, use_org_key=False)
    return result

@mcp.tool()
async def end_live_activity(activity_id: str, subscription_id: str,
                           dismissal_date: int = None, priority: int = None) -> Dict[str, Any]:
    """End an iOS Live Activity.
    
    Args:
        activity_id: ID of the activity to end
        subscription_id: Subscription ID associated with the activity
        dismissal_date: Unix timestamp for dismissal
        priority: Notification priority (5-10)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    # Explicitly include app_id in request body for consistency
    data = {
        "app_id": app_config.app_id,
        "subscription_id": subscription_id,
        "event": "end"
    }
    
    if dismissal_date:
        data["dismissal_date"] = dismissal_date
    if priority:
        data["priority"] = priority
    
    result = await make_onesignal_request(f"live_activities/{activity_id}/end",
                                        method="POST", data=data, use_org_key=False)
    return result

# === NEW: Analytics & Outcomes ===

@mcp.tool()
async def view_outcomes(outcome_names: List[str], outcome_time_range: str = None,
                       outcome_platforms: List[str] = None, 
                       outcome_attribution: str = None) -> Dict[str, Any]:
    """View outcomes data for your OneSignal app.
    
    Args:
        outcome_names: List of outcome names to fetch data for
        outcome_time_range: Time range for data (e.g., "1d", "1mo")
        outcome_platforms: Filter by platforms (e.g., ["ios", "android"])
        outcome_attribution: Attribution model ("direct" or "influenced")
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    params = {"outcome_names": outcome_names}
    
    if outcome_time_range:
        params["outcome_time_range"] = outcome_time_range
    if outcome_platforms:
        params["outcome_platforms"] = outcome_platforms
    if outcome_attribution:
        params["outcome_attribution"] = outcome_attribution
    
    result = await make_onesignal_request(f"apps/{app_config.app_id}/outcomes",
                                        method="GET", params=params, use_org_key=False)
    return result

# === NEW: Export Functions ===

@mcp.tool()
async def export_messages_csv(start_date: str = None, end_date: str = None,
                             event_types: List[str] = None) -> Dict[str, Any]:
    """Export messages/notifications data to CSV (requires Organization API Key).
    
    Args:
        start_date: Start date for export (ISO 8601 format)
        end_date: End date for export (ISO 8601 format)
        event_types: List of event types to export
    """
    data = {}
    
    if start_date:
        data["start_date"] = start_date
    if end_date:
        data["end_date"] = end_date
    if event_types:
        data["event_types"] = event_types
    
    result = await make_onesignal_request("notifications/csv_export",
                                        method="POST", data=data, use_org_key=True)
    return result

@mcp.tool()
async def export_subscriptions_csv(start_date: str = None, end_date: str = None,
                                  segment_names: List[str] = None) -> Dict[str, Any]:
    """Export subscriptions/players data to CSV (requires Organization API Key).
    
    Args:
        start_date: Start date for export (ISO 8601 format)
        end_date: End date for export (ISO 8601 format)
        segment_names: List of segment names to filter by
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    data = {}
    
    if start_date:
        data["start_date"] = start_date
    if end_date:
        data["end_date"] = end_date
    if segment_names:
        data["segment_names"] = segment_names
    
    result = await make_onesignal_request(f"apps/{app_config.app_id}/players/csv_export",
                                        method="POST", data=data, use_org_key=True)
    return result

# === NEW: Player/Device Management (Legacy) ===

@mcp.tool()
async def view_players(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """View players/devices subscribed to your OneSignal app (legacy API).
    
    Args:
        limit: Maximum number of players to return (default: 50, max: 300)
        offset: Result offset for pagination (default: 0)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    params = {
        "app_id": app_config.app_id,
        "limit": min(limit, 300),
        "offset": offset
    }
    
    result = await make_onesignal_request("players", method="GET", params=params, use_org_key=False)
    return result

@mcp.tool()
async def view_player_details(player_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific player/device (legacy API).
    
    Args:
        player_id: The player ID to retrieve details for
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    params = {"app_id": app_config.app_id}
    result = await make_onesignal_request(f"players/{player_id}", method="GET", params=params, use_org_key=False)
    return result

@mcp.tool()
async def add_player(device_type: int, identifier: str = None, 
                    language: str = None, timezone: int = None,
                    game_version: str = None, device_model: str = None,
                    device_os: str = None, ad_id: str = None,
                    sdk: str = None, session_count: int = None,
                    tags: Dict[str, str] = None, amount_spent: float = None,
                    created_at: int = None, last_active: int = None,
                    playtime: int = None, badge_count: int = None,
                    external_user_id: str = None) -> Dict[str, Any]:
    """Add a new player/device to your OneSignal app (legacy API).
    
    Args:
        device_type: Device type (0=iOS, 1=Android, 2=Amazon, 3=WindowsPhone, 4=Chrome, 5=ChromeWeb, 6=Windows, 7=Mac, 8=AmazonFire, 9=Safari, 10=Firefox, 11=Opera, 12=Edge)
        identifier: Push notification identifier (required for push)
        language: Language code (e.g., "en")
        timezone: Timezone offset in seconds
        game_version: Game version string
        device_model: Device model name
        device_os: Device OS version
        ad_id: Advertising ID
        sdk: SDK version
        session_count: Number of sessions
        tags: Custom tags
        amount_spent: Total amount spent
        created_at: Unix timestamp when created
        last_active: Unix timestamp of last activity
        playtime: Total playtime in seconds
        badge_count: Badge count
        external_user_id: External user ID
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    data = {
        "app_id": app_config.app_id,
        "device_type": device_type
    }
    
    if identifier:
        data["identifier"] = identifier
    if language:
        data["language"] = language
    if timezone is not None:
        data["timezone"] = timezone
    if game_version:
        data["game_version"] = game_version
    if device_model:
        data["device_model"] = device_model
    if device_os:
        data["device_os"] = device_os
    if ad_id:
        data["ad_id"] = ad_id
    if sdk:
        data["sdk"] = sdk
    if session_count is not None:
        data["session_count"] = session_count
    if tags:
        data["tags"] = tags
    if amount_spent is not None:
        data["amount_spent"] = amount_spent
    if created_at is not None:
        data["created_at"] = created_at
    if last_active is not None:
        data["last_active"] = last_active
    if playtime is not None:
        data["playtime"] = playtime
    if badge_count is not None:
        data["badge_count"] = badge_count
    if external_user_id:
        data["external_user_id"] = external_user_id
    
    result = await make_onesignal_request("players", method="POST", data=data, use_org_key=False)
    return result

@mcp.tool()
async def edit_player(player_id: str, language: str = None,
                     timezone: int = None, game_version: str = None,
                     device_model: str = None, device_os: str = None,
                     ad_id: str = None, sdk: str = None,
                     session_count: int = None, tags: Dict[str, str] = None,
                     amount_spent: float = None, last_active: int = None,
                     playtime: int = None, badge_count: int = None,
                     external_user_id: str = None) -> Dict[str, Any]:
    """Edit an existing player/device (legacy API).
    
    Args:
        player_id: The player ID to update
        language: Language code
        timezone: Timezone offset in seconds
        game_version: Game version string
        device_model: Device model name
        device_os: Device OS version
        ad_id: Advertising ID
        sdk: SDK version
        session_count: Number of sessions
        tags: Custom tags
        amount_spent: Total amount spent
        last_active: Unix timestamp of last activity
        playtime: Total playtime in seconds
        badge_count: Badge count
        external_user_id: External user ID
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    data = {
        "app_id": app_config.app_id
    }
    
    if language:
        data["language"] = language
    if timezone is not None:
        data["timezone"] = timezone
    if game_version:
        data["game_version"] = game_version
    if device_model:
        data["device_model"] = device_model
    if device_os:
        data["device_os"] = device_os
    if ad_id:
        data["ad_id"] = ad_id
    if sdk:
        data["sdk"] = sdk
    if session_count is not None:
        data["session_count"] = session_count
    if tags:
        data["tags"] = tags
    if amount_spent is not None:
        data["amount_spent"] = amount_spent
    if last_active is not None:
        data["last_active"] = last_active
    if playtime is not None:
        data["playtime"] = playtime
    if badge_count is not None:
        data["badge_count"] = badge_count
    if external_user_id:
        data["external_user_id"] = external_user_id
    
    result = await make_onesignal_request(f"players/{player_id}", method="PUT", data=data, use_org_key=False)
    return result

@mcp.tool()
async def delete_player(player_id: str) -> Dict[str, Any]:
    """Delete a player/device record (legacy API).
    
    Args:
        player_id: The player ID to delete
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    params = {"app_id": app_config.app_id}
    result = await make_onesignal_request(f"players/{player_id}", method="DELETE", params=params, use_org_key=False)
    return result

@mcp.tool()
async def edit_tags_with_external_user_id(external_user_id: str, tags: Dict[str, str]) -> Dict[str, Any]:
    """Edit tags for a user by external user ID (legacy API).
    
    Args:
        external_user_id: External user ID
        tags: Tags to update (use empty string value to remove a tag)
    """
    app_config = get_current_app()
    if not app_config:
        return {"error": "No app currently selected. Use switch_app to select an app."}
    
    data = {
        "app_id": app_config.app_id,
        "tags": tags
    }
    
    result = await make_onesignal_request(f"users/{external_user_id}", method="PUT", data=data, use_org_key=False)
    return result

# === NEW: API Key Management ===

@mcp.tool()
async def delete_app_api_key(app_id: str, key_id: str) -> Dict[str, Any]:
    """Delete an API key from a specific OneSignal app.
    
    Args:
        app_id: The ID of the app
        key_id: The ID of the API key to delete
    """
    result = await make_onesignal_request(f"apps/{app_id}/auth/tokens/{key_id}",
                                        method="DELETE", use_org_key=True)
    if "error" not in result:
        return {"success": f"API key '{key_id}' deleted successfully"}
    return result

@mcp.tool()
async def update_app_api_key(app_id: str, key_id: str, name: str = None,
                            scopes: List[str] = None) -> Dict[str, Any]:
    """Update an API key for a specific OneSignal app.
    
    Args:
        app_id: The ID of the app
        key_id: The ID of the API key to update
        name: New name for the API key
        scopes: New list of permission scopes
    """
    data = {}
    
    if name:
        data["name"] = name
    if scopes:
        data["scopes"] = scopes
    
    if not data:
        return {"error": "No update parameters provided"}
    
    result = await make_onesignal_request(f"apps/{app_id}/auth/tokens/{key_id}",
                                        method="PATCH", data=data, use_org_key=True)
    return result

@mcp.tool()
async def rotate_app_api_key(app_id: str, key_id: str) -> Dict[str, Any]:
    """Rotate an API key (generate new token while keeping permissions).
    
    Args:
        app_id: The ID of the app
        key_id: The ID of the API key to rotate
    """
    result = await make_onesignal_request(f"apps/{app_id}/auth/tokens/{key_id}/rotate",
                                        method="POST", use_org_key=True)
    if "error" not in result:
        return {
            "success": f"API key rotated successfully",
            "new_token": result.get("token"),
            "warning": "Save the new token now! You won't be able to see it again."
        }
    return result

# Run the server
if __name__ == "__main__":
    # Run the server
    mcp.run()