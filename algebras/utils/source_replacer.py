"""
Source code replacer for replacing hardcoded strings with translation function calls
"""

import os
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from algebras.utils.i18n_detector import (
    get_translation_function_call,
    get_import_statement,
    needs_hook,
    get_framework_config
)


def replace_strings_in_file(
    file_path: str,
    replacements: List[Tuple[int, str, str]],  # List of (line_number, original_text, translation_key)
    framework: str,
    framework_config: Dict[str, str],
    dry_run: bool = False
) -> Tuple[str, bool]:
    """
    Replace hardcoded strings in a source file with translation function calls.
    
    Args:
        file_path: Path to the source file
        replacements: List of (line_number, original_text, translation_key) tuples
        framework: i18n framework name
        framework_config: Framework configuration
        dry_run: If True, don't modify file, just return the modified content
        
    Returns:
        Tuple of (modified_content, has_changes)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    lines = content.split('\n')
    
    # Sort replacements by line number (descending) to avoid line number shifts
    replacements_sorted = sorted(replacements, key=lambda x: x[0], reverse=True)
    
    # Track if we need to add import
    needs_import = False
    needs_hook_in_component = False
    
    # Ensure framework_config has all required keys
    if not framework_config:
        framework_config = get_framework_config(framework)
    
    # Check if import already exists
    import_stmt = get_import_statement(framework, framework_config)
    # Check if the import package or hook is already imported
    import_pkg = framework_config.get('import', '')
    hook_name = framework_config.get('hook', '')
    import_exists = import_pkg in content or (hook_name and hook_name in content)
    
    # Check if hook is already called in the file
    hook_call_exists = False
    if needs_hook(framework) and hook_name:
        # Look for patterns like: const t = useTranslations(); or const { t } = useTranslation();
        hook_patterns = [
            f"const t = {hook_name}()",
            f"const {{ t }} = {hook_name}()",
            f"const intl = {hook_name}()",
            f"{hook_name}()"
        ]
        hook_call_exists = any(pattern in content for pattern in hook_patterns)
    
    # Process replacements from bottom to top to preserve line numbers
    for line_num, original_text, translation_key in replacements_sorted:
        if line_num > len(lines):
            continue
        
        line_index = line_num - 1  # Convert to 0-based index
        line = lines[line_index]
        
        # Create replacement string
        replacement = get_translation_function_call(framework, framework_config, translation_key, use_var=True)
        
        # Handle different contexts
        if original_text in line:
            # Simple string replacement
            # Handle JSX text: <h1>Text</h1> -> <h1>{t('key')}</h1>
            if f">{original_text}<" in line or f">{original_text}</" in line:
                # JSX text content
                new_line = line.replace(original_text, f"{{{replacement}}}")
            # Handle string literals in JSX attributes: title="Text" -> title={t('key')}
            elif f'="{original_text}"' in line or f"='{original_text}'" in line:
                # JSX attribute
                new_line = re.sub(
                    rf'(["\']){re.escape(original_text)}\1',
                    f"{{{replacement}}}",
                    line
                )
            # Handle string literals: "Text" -> t('key')
            elif f'"{original_text}"' in line or f"'{original_text}'" in line:
                # Regular string literal
                new_line = re.sub(
                    rf'["\']{re.escape(original_text)}["\']',
                    replacement,
                    line
                )
            else:
                # Try to find and replace the text
                new_line = line.replace(original_text, replacement)
            
            lines[line_index] = new_line
            needs_import = True
            
            # Check if we need hook call in component
            if needs_hook(framework) and not hook_call_exists:
                needs_hook_in_component = True
    
    # Add import statement if needed
    if needs_import and not import_exists:
        # Find the best place to add import (after existing imports)
        import_lines = []
        last_import_index = -1
        
        for i, line in enumerate(lines):
            if line.strip().startswith('import ') or line.strip().startswith('import{'):
                import_lines.append(line)
                last_import_index = i
        
        if last_import_index >= 0:
            # Add after last import
            lines.insert(last_import_index + 1, import_stmt)
            # Add hook call if needed (for React components)
            if needs_hook(framework) and needs_hook_in_component and not hook_call_exists:
                hook_name = framework_config.get('hook', '')
                if hook_name:
                    # Find function/component start to add hook call
                    # Look for export default, function, or const component declarations
                    for i in range(last_import_index + 2, min(last_import_index + 20, len(lines))):
                        line_content = lines[i].strip()
                        if (line_content.startswith('export default') or 
                            (line_content.startswith('function ') and 'Component' in line_content) or
                            (line_content.startswith('const ') and 'Component' in line_content) or
                            (line_content.startswith('function ') and i < len(lines) - 1 and '{' in lines[i+1]) or
                            (line_content.startswith('const ') and '=' in line_content and '=>' in line_content)):
                            # Add hook call after function/component declaration
                            indent = len(lines[i]) - len(lines[i].lstrip())
                            if framework == 'next-intl':
                                hook_call = f"{' ' * indent}const t = {hook_name}();"
                            elif framework == 'react-i18next':
                                hook_call = f"{' ' * indent}const {{ t }} = {hook_name}();"
                            elif framework == 'react-intl':
                                hook_call = f"{' ' * indent}const intl = {hook_name}();"
                            else:
                                hook_call = f"{' ' * indent}const t = {hook_name}();"
                            # Find the opening brace and add hook call after it
                            for j in range(i + 1, min(i + 5, len(lines))):
                                if '{' in lines[j]:
                                    lines.insert(j + 1, hook_call)
                                    break
                            else:
                                # No brace found, add after the declaration
                                lines.insert(i + 1, hook_call)
                            break
        else:
            # No imports found, add at the top
            lines.insert(0, import_stmt)
            if needs_hook(framework) and has_hook_call:
                hook_name = framework_config.get('hook', 'useTranslations')
                if framework == 'next-intl':
                    hook_call = f"const t = {hook_name}();"
                elif framework == 'react-i18next':
                    hook_call = f"const {{ t }} = {hook_name}();"
                elif framework == 'react-intl':
                    hook_call = f"const intl = {hook_name}();"
                else:
                    hook_call = f"const t = {hook_name}();"
                lines.insert(1, hook_call)
    
    modified_content = '\n'.join(lines)
    has_changes = modified_content != original_content
    
    if not dry_run and has_changes:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
    
    return modified_content, has_changes

