# OneSignal MCP Server

A Model Context Protocol (MCP) server for interacting with the OneSignal API. This server provides a convenient interface for managing push notifications, emails, SMS, user devices, segments, templates, and more through OneSignal's REST API.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/weirdbrains/onesignal-mcp)

## Overview

This MCP server wraps the [OneSignal REST API](https://documentation.onesignal.com/reference/rest-api-overview) to provide a set of tools for managing your OneSignal applications and sending messages to your users. It supports all major OneSignal operations including:

- Sending push notifications, emails, and SMS
- Managing user devices and subscriptions
- Creating and managing segments
- Creating and managing templates
- Viewing app information and analytics
- Organization-level operations
- **Managing multiple OneSignal applications**

## Requirements

- Python 3.7 or higher
- `python-dotenv` package
- `requests` package
- OneSignal account with API credentials

## Installation

### Option 1: Clone from GitHub

```bash
# Clone the repository
git clone https://github.com/weirdbrains/onesignal-mcp.git
cd onesignal-mcp

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Install as a Package (Coming Soon)

```bash
pip install onesignal-mcp
```

## Configuration

1. Create a `.env` file in the root directory with your OneSignal credentials:
   ```
   # Default app credentials (optional, you can also add apps via the API)
   ONESIGNAL_APP_ID=your_app_id_here
   ONESIGNAL_API_KEY=your_rest_api_key_here
   
   # Organization API key (for org-level operations)
   ONESIGNAL_ORG_API_KEY=your_organization_api_key_here
   ```

2. You can find your OneSignal credentials in your OneSignal dashboard:
   - App ID: Settings > Keys & IDs > OneSignal App ID
   - REST API Key: Settings > Keys & IDs > REST API Key
   - Organization API Key: Organization Settings > API Keys

## Usage

### Running the Server

```bash
python onesignal_server.py
```

The server will start and register itself with the MCP system, making its tools available for use.

### Basic Usage Examples

#### Sending a Push Notification

```python
# Send a notification to all subscribed users
result = await send_notification(
    title="Hello World",
    message="This is a test notification",
    segment="Subscribed Users"
)
print(result)
```

#### Working with Multiple Apps

```python
# Add a new app configuration
await add_app(
    key="my_second_app", 
    app_id="second-app-id", 
    api_key="second-app-api-key", 
    name="My Second App"
)

# List all configured apps
apps = await list_apps()
print(apps)

# Switch to the new app
await switch_app("my_second_app")

# Send a notification using the current app
await send_notification(
    title="Hello", 
    message="This is from my second app"
)

# Send a notification from a specific app (without switching)
await send_notification(
    title="Hello", 
    message="This is from my first app", 
    app_key="mandible"
)
```

#### Managing Segments

```python
# List all segments
segments = await view_segments()
print(segments)

# Create a new segment
result = await create_segment(
    name="High Value Users",
    filters='[{"field":"amount_spent", "relation":">", "value":"100"}]'
)
print(result)
```

#### Working with Templates

```python
# Create an email template
result = await create_template(
    name="Welcome Email",
    title="Welcome to Our App",
    message="<html><body><h1>Welcome!</h1><p>Thank you for joining us.</p></body></html>",
    template_type="email"
)
print(result)
```

## Multi-App Support

This server supports managing multiple OneSignal applications. You can:

1. Add multiple app configurations with different identifiers
2. Switch between apps when making API calls
3. Specify which app to use for individual operations

### App Management Tools

- `list_apps`: List all configured OneSignal apps in the server
- `add_app`: Add a new OneSignal app configuration
- `update_app`: Update an existing OneSignal app configuration
- `remove_app`: Remove an OneSignal app configuration
- `switch_app`: Switch the current app to use for API requests

## Available Tools

### Message Management

- `send_notification`: Send a new push notification, email, or SMS
- `view_messages`: List recent messages sent through OneSignal
- `view_message_details`: Get detailed information about a specific message
- `cancel_message`: Cancel a scheduled message

### Device Management

- `view_devices`: List devices (users) registered in your OneSignal app
- `view_device_details`: Get detailed information about a specific device

### Segment Management

- `view_segments`: List all segments available in your OneSignal app
- `create_segment`: Create a new segment with specified filters
- `delete_segment`: Delete an existing segment

### Template Management

- `view_templates`: List all templates available in your OneSignal app
- `view_template_details`: Get detailed information about a specific template
- `create_template`: Create a new template for notifications or emails

### App Information

- `view_app_details`: Get detailed information about the configured OneSignal app

## Logging

The server includes comprehensive logging to help with debugging and monitoring. Logs are output to the console by default, with the following format:

```
YYYY-MM-DD HH:MM:SS - onesignal-mcp - LEVEL - Message
```

You can adjust the logging level by modifying the `logging.basicConfig` call in the server file.

## Testing

The OneSignal MCP server includes a comprehensive test suite to ensure all functionality works as expected. The tests use Python's built-in `unittest` framework and mock external API calls to test the server's behavior.

### Running Tests

To run the tests, use the following command:

```bash
python -m unittest discover tests
```

This will discover and run all tests in the `tests` directory.

### Test Coverage

The test suite covers:
- App configuration management
- API request handling with proper authentication
- Error handling and recovery
- Multiple app support
- Organization-level operations

### Writing New Tests

If you add new functionality to the server, please also add corresponding tests. Tests should be placed in the `tests` directory and follow the naming convention `test_*.py`.

## Troubleshooting

### Common Issues

#### No App Configuration Available

If you see the error "No app configuration available", make sure you have:
1. Set up your `.env` file with the correct credentials, or
2. Added an app configuration using the `add_app` tool

#### API Key Errors

If you receive authentication errors, verify that:
1. Your API keys are correct
2. You're using the right key for the operation (REST API Key vs Organization API Key)
3. The key has the necessary permissions in OneSignal

#### Rate Limiting

OneSignal has rate limits for API requests. If you encounter rate limiting:
1. Reduce the frequency of your requests
2. Implement retry logic with exponential backoff

### Getting Help

If you encounter issues not covered here:
1. Check the [OneSignal API Documentation](https://documentation.onesignal.com/reference)
2. Open an issue on the GitHub repository

## Contributing

We welcome contributions to improve the OneSignal MCP server! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [OneSignal](https://onesignal.com/) for their excellent notification service and API
- The Weirdbrains team for supporting this project
