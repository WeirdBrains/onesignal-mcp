import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json
import asyncio

# Add the parent directory to sys.path to import the server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the server module
import onesignal_server

class TestOneSignalServer(unittest.TestCase):
    """Test cases for the OneSignal MCP server."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'ONESIGNAL_APP_ID': 'test-app-id',
            'ONESIGNAL_API_KEY': 'test-api-key',
            'ONESIGNAL_ORG_API_KEY': 'test-org-api-key'
        })
        self.env_patcher.start()
        
        # Reset app configurations for each test
        onesignal_server.app_configs = {}
        onesignal_server.current_app_key = None
        
        # Initialize with test app
        onesignal_server.add_app_config('test', 'test-app-id', 'test-api-key', 'Test App')
        onesignal_server.current_app_key = 'test'
    
    def tearDown(self):
        """Clean up after each test."""
        self.env_patcher.stop()
    
    def test_app_config(self):
        """Test AppConfig class."""
        app = onesignal_server.AppConfig('app-id', 'api-key', 'App Name')
        self.assertEqual(app.app_id, 'app-id')
        self.assertEqual(app.api_key, 'api-key')
        self.assertEqual(app.name, 'App Name')
        self.assertEqual(str(app), 'App Name (app-id)')
    
    def test_add_app_config(self):
        """Test adding app configurations."""
        onesignal_server.add_app_config('new-app', 'new-app-id', 'new-api-key', 'New App')
        self.assertIn('new-app', onesignal_server.app_configs)
        self.assertEqual(onesignal_server.app_configs['new-app'].app_id, 'new-app-id')
        self.assertEqual(onesignal_server.app_configs['new-app'].api_key, 'new-api-key')
        self.assertEqual(onesignal_server.app_configs['new-app'].name, 'New App')
    
    def test_set_current_app(self):
        """Test setting the current app."""
        # Add a second app
        onesignal_server.add_app_config('second', 'second-app-id', 'second-api-key')
        
        # Test switching to an existing app
        result = onesignal_server.set_current_app('second')
        self.assertTrue(result)
        self.assertEqual(onesignal_server.current_app_key, 'second')
        
        # Test switching to a non-existent app
        result = onesignal_server.set_current_app('non-existent')
        self.assertFalse(result)
        self.assertEqual(onesignal_server.current_app_key, 'second')  # Should not change
    
    def test_get_current_app(self):
        """Test getting the current app configuration."""
        current_app = onesignal_server.get_current_app()
        self.assertIsNotNone(current_app)
        self.assertEqual(current_app.app_id, 'test-app-id')
        self.assertEqual(current_app.api_key, 'test-api-key')
        
        # Test with no current app
        onesignal_server.current_app_key = None
        current_app = onesignal_server.get_current_app()
        self.assertIsNone(current_app)
    
    @patch('requests.get')
    def test_make_onesignal_request_get(self, mock_get):
        """Test making a GET request to the OneSignal API."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {'success': True}
        mock_response.text = json.dumps({'success': True})
        mock_get.return_value = mock_response
        
        # Make the request and run it through the event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                onesignal_server.make_onesignal_request('notifications', 'GET', params={'limit': 10})
            )
            
            # Check that the request was made correctly
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            self.assertEqual(kwargs['headers']['Authorization'], 'Key test-api-key')
            self.assertEqual(kwargs['params']['app_id'], 'test-app-id')
            self.assertEqual(kwargs['params']['limit'], 10)
            
            # Check the result
            self.assertEqual(result, {'success': True})
        finally:
            loop.close()
    
    @patch('requests.post')
    def test_make_onesignal_request_post(self, mock_post):
        """Test making a POST request to the OneSignal API."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {'id': 'notification-id'}
        mock_response.text = json.dumps({'id': 'notification-id'})
        mock_post.return_value = mock_response
        
        # Make the request
        data = {'contents': {'en': 'Test message'}}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                onesignal_server.make_onesignal_request('notifications', 'POST', data=data)
            )
            
            # Check that the request was made correctly
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertEqual(kwargs['headers']['Authorization'], 'Key test-api-key')
            self.assertEqual(kwargs['json']['app_id'], 'test-app-id')
            self.assertEqual(kwargs['json']['contents']['en'], 'Test message')
            
            # Check the result
            self.assertEqual(result, {'id': 'notification-id'})
        finally:
            loop.close()
    
    @patch('requests.get')
    @patch('onesignal_server.ONESIGNAL_ORG_API_KEY', 'test-org-api-key')
    def test_make_onesignal_request_with_org_key(self, mock_get):
        """Test making a request with the organization API key."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {'apps': []}
        mock_response.text = json.dumps({'apps': []})
        mock_get.return_value = mock_response
        
        # Make the request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                onesignal_server.make_onesignal_request('apps', 'GET', use_org_key=True)
            )
            
            # Check that the request was made correctly
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            self.assertEqual(kwargs['headers']['Authorization'], 'Key test-org-api-key')
            
            # Check the result
            self.assertEqual(result, {'apps': []})
        finally:
            loop.close()
    
    @patch('requests.get')
    def test_make_onesignal_request_error_handling(self, mock_get):
        """Test error handling in make_onesignal_request."""
        # Mock a request exception
        mock_get.side_effect = Exception('Test error')
        
        # Make the request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                onesignal_server.make_onesignal_request('notifications')
            )
            
            # Check the result
            self.assertIn('error', result)
            self.assertEqual(result['error'], 'Unexpected error: Test error')
        finally:
            loop.close()

if __name__ == '__main__':
    unittest.main()
