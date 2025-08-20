"""
Application Settings Management
Handles configuration variables that can be modified through the UI
"""
import json
import os
from typing import Dict, Any
from datetime import datetime


class ApplicationSettings:
    """Manages application-wide configurable settings"""

    def __init__(self, settings_file: str =
                 'config/application_settings.json'):
        self.settings_file = settings_file
        self.settings = self.load_settings()

    def get_default_settings(self) -> Dict[str, Any]:
        """Return default application settings"""
        return {
            # Application Identity
            'application_name': 'ACME App',
            'application_version': '2.0',
            'company_name': 'ACME Corporation',
            'application_description': 'Advanced Configuration Management Env',

            # UI Configuration
            'theme_color': '#2563eb',
            'sidebar_width': '280',
            'items_per_page': '10',
            'default_language': 'en',
            'enable_dark_mode': False,

            # File Upload Settings
            'max_file_size_mb': '16',
            'allowed_file_extensions': 'csv,xlsx,xls,txt',
            'auto_process_uploads': True,
            'keep_uploaded_files_days': '30',

            # Security Settings
            'session_timeout_hours': '24',
            'password_min_length': '12',
            'login_attempt_limit': '5',
            'account_lockout_minutes': '30',
            'require_strong_passwords': True,

            # System Settings
            'enable_api_access': True,
            'log_level': 'INFO',
            'enable_file_logging': True,
            'backup_interval_hours': '24',
            'enable_email_notifications': False,

            # Email Configuration
            'smtp_server': '',
            'smtp_port': '587',
            'smtp_username': '',
            'smtp_use_tls': True,
            'default_sender_email': '',

            # AI Configuration
            'ai_model_provider': 'openai',
            'ai_max_tokens': '4000',
            'ai_temperature': '0.7',
            'enable_ai_features': True,

            # Navigation Settings
            'show_test_api_menu': True,
            'show_navigation_editor': True,
            'default_dashboard_tab': 'dashboard',
            'enable_breadcrumbs': True,

            # Advanced Settings
            'debug_mode': False,
            'maintenance_mode': False,
            'enable_cache': True,
            'cache_timeout_minutes': '60',

            # Metadata
            'last_updated': datetime.now().isoformat(),
            'updated_by': 'system'
        }

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file or create with defaults"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    default_settings = self.get_default_settings()
                    default_settings.update(loaded_settings)
                    return default_settings
            else:
                # Create file with defaults
                default_settings = self.get_default_settings()
                self.save_settings(default_settings)
                return default_settings
        except Exception as e:
            print(f"Error loading settings: {e}")
            return self.get_default_settings()

    def save_settings(self, settings: Dict[str, Any] = None) -> bool:
        """Save settings to file"""
        try:
            if settings is None:
                settings = self.settings

            # Update metadata
            settings['last_updated'] = datetime.now().isoformat()

            # Ensure directory exists
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)

            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)

            self.settings = settings
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """Set a setting value"""
        try:
            self.settings[key] = value
            return self.save_settings()
        except Exception as e:
            print(f"Error setting value for {key}: {e}")
            return False

    def update_multiple(self, updates: Dict[str, Any], updated_by: str = 'admin') -> bool:
        """Update multiple settings at once"""
        try:
            self.settings.update(updates)
            self.settings['updated_by'] = updated_by
            return self.save_settings()
        except Exception as e:
            print(f"Error updating multiple settings: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """Reset all settings to defaults"""
        try:
            self.settings = self.get_default_settings()
            return self.save_settings()
        except Exception as e:
            print(f"Error resetting to defaults: {e}")
            return False

    def get_setting_categories(self) -> Dict[str, list]:
        """Get settings organized by categories"""
        return {
            'Application Identity': [
                'application_name', 'application_version', 'company_name', 'application_description'
            ],
            'User Interface': [
                'theme_color', 'sidebar_width', 'items_per_page', 'default_language',
                'enable_dark_mode', 'enable_breadcrumbs'
            ],
            'File Management': [
                'max_file_size_mb', 'allowed_file_extensions', 'auto_process_uploads',
                'keep_uploaded_files_days'
            ],
            'Security': [
                'session_timeout_hours', 'password_min_length', 'login_attempt_limit',
                'account_lockout_minutes', 'require_strong_passwords'
            ],
            'System': [
                'enable_api_access', 'log_level', 'enable_file_logging',
                'backup_interval_hours', 'enable_email_notifications'
            ],
            'Email': [
                'smtp_server', 'smtp_port', 'smtp_username', 'smtp_use_tls', 'default_sender_email'
            ],
            'AI Configuration': [
                'ai_model_provider', 'ai_max_tokens', 'ai_temperature', 'enable_ai_features'
            ],
            'Navigation': [
                'show_test_api_menu', 'show_navigation_editor', 'default_dashboard_tab'
            ],
            'Advanced': [
                'debug_mode', 'maintenance_mode', 'enable_cache', 'cache_timeout_minutes'
            ]
        }

    def get_setting_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all settings (type, description, validation)"""
        return {
            'application_name': {
                'type': 'text',
                'label': 'Application Name',
                'description': 'The name displayed throughout the application',
                'required': True,
                'max_length': 50
            },
            'application_version': {
                'type': 'text',
                'label': 'Application Version',
                'description': 'Current version of the application',
                'required': True,
                'pattern': r'^\d+\.\d+(\.\d+)?$'
            },
            'company_name': {
                'type': 'text',
                'label': 'Company Name',
                'description': 'Name of the organization using this application',
                'required': False,
                'max_length': 100
            },
            'application_description': {
                'type': 'textarea',
                'label': 'Application Description',
                'description': 'Brief description of the application purpose',
                'required': False,
                'max_length': 500
            },
            'theme_color': {
                'type': 'color',
                'label': 'Theme Color',
                'description': 'Primary color for the application theme',
                'required': True
            },
            'sidebar_width': {
                'type': 'number',
                'label': 'Sidebar Width (px)',
                'description': 'Width of the navigation sidebar in pixels',
                'min': 200,
                'max': 400
            },
            'items_per_page': {
                'type': 'select',
                'label': 'Items Per Page',
                'description': 'Default number of items to show per page',
                'options': ['5', '10', '20', '50', '100']
            },
            'enable_dark_mode': {
                'type': 'checkbox',
                'label': 'Enable Dark Mode',
                'description': 'Allow users to switch to dark theme'
            },
            'max_file_size_mb': {
                'type': 'number',
                'label': 'Max File Size (MB)',
                'description': 'Maximum allowed file upload size in megabytes',
                'min': 1,
                'max': 100
            },
            'session_timeout_hours': {
                'type': 'number',
                'label': 'Session Timeout (Hours)',
                'description': 'Number of hours before user sessions expire',
                'min': 1,
                'max': 168
            },
            'password_min_length': {
                'type': 'number',
                'label': 'Minimum Password Length',
                'description': 'Minimum required length for user passwords',
                'min': 8,
                'max': 50
            },
            'debug_mode': {
                'type': 'checkbox',
                'label': 'Debug Mode',
                'description': 'Enable detailed error logging and debugging features'
            },
            'maintenance_mode': {
                'type': 'checkbox',
                'label': 'Maintenance Mode',
                'description': 'Put application in maintenance mode (blocks normal access)'
            }
        }

# Global instance
app_settings = ApplicationSettings()
