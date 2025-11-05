"""
i18n framework detector for automatic framework detection
"""

import os
import json
import re
from typing import Optional, Dict, Tuple


def detect_framework(project_root: str = None) -> Tuple[Optional[str], Dict[str, str]]:
    """
    Detect the i18n framework being used in the project.
    
    Args:
        project_root: Root directory of the project (defaults to current directory)
        
    Returns:
        Tuple of (framework_name, config_dict)
        framework_name: 'next-intl', 'i18next', 'react-i18next', 'react-intl', or None
        config_dict: Framework-specific configuration
    """
    if project_root is None:
        project_root = os.getcwd()
    
    # Check package.json for dependencies
    package_json_path = os.path.join(project_root, 'package.json')
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, 'r', encoding='utf-8') as f:
                package_json = json.load(f)
            
            dependencies = {}
            dependencies.update(package_json.get('dependencies', {}))
            dependencies.update(package_json.get('devDependencies', {}))
            
            # Check for next-intl
            if 'next-intl' in dependencies:
                return 'next-intl', {
                    'hook': 'useTranslations',
                    'function': 't',
                    'import': 'next-intl'
                }
            
            # Check for react-i18next
            if 'react-i18next' in dependencies:
                return 'react-i18next', {
                    'hook': 'useTranslation',
                    'function': 't',
                    'import': 'react-i18next'
                }
            
            # Check for i18next
            if 'i18next' in dependencies:
                return 'i18next', {
                    'hook': None,
                    'function': 'i18n.t',
                    'import': 'i18next'
                }
            
            # Check for react-intl
            if 'react-intl' in dependencies:
                return 'react-intl', {
                    'hook': 'useIntl',
                    'function': 'formatMessage',
                    'import': 'react-intl'
                }
        except Exception:
            pass
    
    # Check for translation files to infer framework
    common_paths = [
        'messages',
        'locales',
        'i18n',
        'translations',
        'src/locales',
        'src/messages',
        'src/i18n',
        'app/locales',
        'app/messages',
        'public/locales'
    ]
    
    for path in common_paths:
        full_path = os.path.join(project_root, path)
        if os.path.exists(full_path):
            # Check for next-intl structure (messages/{lang}.json)
            if os.path.isdir(full_path):
                for item in os.listdir(full_path):
                    item_path = os.path.join(full_path, item)
                    if os.path.isdir(item_path) or item.endswith('.json'):
                        # Likely next-intl or i18next structure
                        # Check if it's next-intl by looking for next.config.js
                        next_config = os.path.join(project_root, 'next.config.js')
                        if os.path.exists(next_config):
                            return 'next-intl', {
                                'hook': 'useTranslations',
                                'function': 't',
                                'import': 'next-intl'
                            }
                        return 'i18next', {
                            'hook': 'useTranslation',
                            'function': 't',
                            'import': 'react-i18next'
                        }
    
    return None, {}


def get_framework_config(framework: str) -> Dict[str, str]:
    """
    Get default configuration for a framework.
    
    Args:
        framework: Framework name
        
    Returns:
        Framework configuration dict
    """
    if framework == 'next-intl':
        return {
            'hook': 'useTranslations',
            'function': 't',
            'import': 'next-intl'
        }
    elif framework == 'react-i18next':
        return {
            'hook': 'useTranslation',
            'function': 't',
            'import': 'react-i18next'
        }
    elif framework == 'i18next':
        return {
            'hook': None,
            'function': 'i18n.t',
            'import': 'i18next'
        }
    elif framework == 'react-intl':
        return {
            'hook': 'useIntl',
            'function': 'formatMessage',
            'import': 'react-intl'
        }
    else:
        return {
            'hook': None,
            'function': 't',
            'import': './i18n'
        }


def get_translation_function_call(framework: str, config: Dict[str, str], key: str, use_var: bool = True) -> str:
    """
    Get the appropriate translation function call for a framework.
    
    Args:
        framework: Framework name ('next-intl', 'i18next', etc.)
        config: Framework configuration dict
        key: Translation key
        use_var: If True, use variable name (t, intl), otherwise use full function call
        
    Returns:
        String representation of the translation function call
    """
    if framework == 'next-intl':
        func = config.get('function', 't')
        var_name = 't' if use_var else func
        return f"{var_name}('{key}')"
    
    elif framework == 'react-i18next':
        func = config.get('function', 't')
        var_name = 't' if use_var else func
        return f"{var_name}('{key}')"
    
    elif framework == 'i18next':
        func = config.get('function', 'i18n.t')
        return f"{func}('{key}')"
    
    elif framework == 'react-intl':
        func = config.get('function', 'formatMessage')
        var_name = 'intl' if use_var else func
        return f"{var_name}.{func}({{ id: '{key}' }})"
    
    else:
        # Generic fallback
        return f"t('{key}')"


def get_import_statement(framework: str, config: Dict[str, str]) -> str:
    """
    Get the import statement needed for the framework.
    
    Args:
        framework: Framework name
        config: Framework configuration dict
        
    Returns:
        Import statement string
    """
    if framework == 'next-intl':
        hook = config.get('hook', 'useTranslations')
        import_pkg = config.get('import', 'next-intl')
        return f"import {{ {hook} }} from '{import_pkg}';"
    
    elif framework == 'react-i18next':
        hook = config.get('hook', 'useTranslation')
        import_pkg = config.get('import', 'react-i18next')
        return f"import {{ {hook} }} from '{import_pkg}';"
    
    elif framework == 'i18next':
        import_pkg = config.get('import', 'i18next')
        return f"import i18n from '{import_pkg}';"
    
    elif framework == 'react-intl':
        hook = config.get('hook', 'useIntl')
        import_pkg = config.get('import', 'react-intl')
        return f"import {{ {hook} }} from '{import_pkg}';"
    
    else:
        # Generic fallback
        return "import { t } from './i18n';"


def needs_hook(framework: str) -> bool:
    """
    Check if the framework requires a hook to be called.
    
    Args:
        framework: Framework name
        
    Returns:
        True if hook is needed, False otherwise
    """
    return framework in ['next-intl', 'react-i18next', 'react-intl']

