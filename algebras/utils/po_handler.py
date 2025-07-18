"""
.po (gettext) localization file handler
"""

import re
from typing import Dict, Any, List, Tuple


def read_po_file(file_path: str) -> Dict[str, Any]:
    """
    Read a .po (gettext) localization file and extract key-value pairs.
    
    Args:
        file_path: Path to the .po file
        
    Returns:
        Dictionary containing the translation content
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse the .po file content
    entries = _parse_po_content(content)
    
    # Convert to simple key-value dictionary for translation
    result = {}
    for entry in entries:
        if entry['msgid'] and entry['msgstr'] is not None:
            result[entry['msgid']] = entry['msgstr']
    
    return result


def write_po_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write a dictionary to a .po localization file while preserving structure.
    
    Args:
        file_path: Path to the .po file
        content: Dictionary to write
    """
    import os
    
    # Check if target file exists
    if os.path.exists(file_path):
        # Read the original file to preserve structure
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Parse the original content to get structure
        entries = _parse_po_content(original_content)
        
        # Track which keys we've updated
        updated_keys = set()
        
        # Update msgstr values with new translations
        for entry in entries:
            if entry['msgid'] in content:
                entry['msgstr'] = content[entry['msgid']]
                updated_keys.add(entry['msgid'])
        
        # Find keys that need to be added (exist in content but not in original file)
        new_keys = set(content.keys()) - updated_keys
        
        # Add new entries for missing keys
        for msgid in sorted(new_keys):
            if not msgid:  # Skip empty keys
                continue
                
            new_entry = {
                'msgid': msgid,
                'msgstr': content[msgid],
                'comments': [],
                'start_line': len(entries),
                'end_line': len(entries)
            }
            entries.append(new_entry)
        
        # Reconstruct the .po file content
        new_content = _reconstruct_po_content(entries, original_content)
    else:
        # Target file doesn't exist, try to find source file to use as template
        # Look for the source file by replacing the language code
        dir_path = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        
        # Try common source language patterns (en.po, es.po, etc.)
        source_candidates = []
        if '.' in filename:
            name_parts = filename.split('.')
            if len(name_parts) >= 2:
                # Try replacing the language part with common source languages
                for src_lang in ['en', 'es', 'fr', 'de']:
                    candidate_name = f"{name_parts[0]}.{src_lang}.{'.'.join(name_parts[2:])}" if len(name_parts) > 2 else f"{src_lang}.{name_parts[1]}"
                    candidate_path = os.path.join(dir_path, candidate_name)
                    if os.path.exists(candidate_path):
                        source_candidates.append(candidate_path)
                
                # Also try just replacing the first part (kk.po -> en.po)
                for src_lang in ['en', 'es', 'fr', 'de']:
                    candidate_path = os.path.join(dir_path, f"{src_lang}.{name_parts[1]}")
                    if os.path.exists(candidate_path):
                        source_candidates.append(candidate_path)
        
        # Use the first available source file as template
        template_content = None
        if source_candidates:
            with open(source_candidates[0], 'r', encoding='utf-8') as f:
                template_content = f.read()
        
        if template_content:
            # Parse the template content to get structure
            entries = _parse_po_content(template_content)
            
            # Track which keys we've updated
            updated_keys = set()
            
            # Update msgstr values with new translations
            for entry in entries:
                if entry['msgid'] in content:
                    entry['msgstr'] = content[entry['msgid']]
                    updated_keys.add(entry['msgid'])
            
            # Find keys that need to be added (exist in content but not in template)
            new_keys = set(content.keys()) - updated_keys
            
            # Add new entries for missing keys
            for msgid in sorted(new_keys):
                if not msgid:  # Skip empty keys
                    continue
                    
                new_entry = {
                    'msgid': msgid,
                    'msgstr': content[msgid],
                    'comments': [],
                    'start_line': len(entries),
                    'end_line': len(entries)
                }
                entries.append(new_entry)
            
            # Reconstruct the .po file content
            new_content = _reconstruct_po_content(entries, template_content)
        else:
            # No template found, create a simple .po file from scratch
            new_content = _create_po_from_scratch(content)
    
    # Ensure directory exists
    dir_path = os.path.dirname(file_path)
    if dir_path:  # Only create directory if there is one
        os.makedirs(dir_path, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)


def _parse_po_content(content: str) -> List[Dict[str, Any]]:
    """
    Parse .po file content into entries with metadata.
    
    Args:
        content: Raw .po file content
        
    Returns:
        List of entries with msgid, msgstr, comments, and position info
    """
    entries = []
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Start of a new entry
        if line.startswith('#') or line.startswith('msgid'):
            entry = {
                'comments': [],
                'msgid': '',
                'msgstr': '',
                'msgid_lines': [],
                'msgstr_lines': [],
                'start_line': i,
                'end_line': i
            }
            
            # Collect comments
            while i < len(lines) and lines[i].strip().startswith('#'):
                entry['comments'].append(lines[i])
                i += 1
            
            # Parse msgid
            if i < len(lines) and lines[i].strip().startswith('msgid'):
                msgid_line = lines[i].strip()
                entry['msgid_lines'].append(msgid_line)
                entry['msgid'] = _extract_quoted_string(msgid_line)
                i += 1
                
                # Handle multi-line msgid
                while i < len(lines) and lines[i].strip().startswith('"'):
                    continued_line = lines[i].strip()
                    entry['msgid_lines'].append(continued_line)
                    entry['msgid'] += _extract_quoted_string(continued_line)
                    i += 1
            
            # Parse msgstr
            if i < len(lines) and lines[i].strip().startswith('msgstr'):
                msgstr_line = lines[i].strip()
                entry['msgstr_lines'].append(msgstr_line)
                entry['msgstr'] = _extract_quoted_string(msgstr_line)
                i += 1
                
                # Handle multi-line msgstr
                while i < len(lines) and lines[i].strip().startswith('"'):
                    continued_line = lines[i].strip()
                    entry['msgstr_lines'].append(continued_line)
                    entry['msgstr'] += _extract_quoted_string(continued_line)
                    i += 1
            
            entry['end_line'] = i - 1
            entries.append(entry)
        else:
            i += 1
    
    return entries


def _extract_quoted_string(line: str) -> str:
    """
    Extract string content from a quoted line.
    
    Args:
        line: Line containing quoted string
        
    Returns:
        Unescaped string content
    """
    # Find the quoted string content
    match = re.search(r'"(.*)"', line)
    if match:
        quoted_content = match.group(1)
        # Unescape the content
        return _unescape_po_string(quoted_content)
    return ''


def _unescape_po_string(text: str) -> str:
    """
    Unescape .po string content.
    
    Args:
        text: Escaped string
        
    Returns:
        Unescaped string
    """
    # Handle common escape sequences
    replacements = [
        ('\\\\', '\\'),
        ('\\"', '"'),
        ('\\n', '\n'),
        ('\\t', '\t'),
        ('\\r', '\r'),
    ]
    
    result = text
    for escaped, unescaped in replacements:
        result = result.replace(escaped, unescaped)
    
    return result


def _escape_po_string(text: str) -> str:
    """
    Escape text for .po string format.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text
    """
    # Handle escape sequences (order matters - backslash first)
    replacements = [
        ('\\', '\\\\'),
        ('"', '\\"'),
        ('\n', '\\n'),
        ('\t', '\\t'),
        ('\r', '\\r'),
    ]
    
    result = text
    for unescaped, escaped in replacements:
        result = result.replace(unescaped, escaped)
    
    return result


def _reconstruct_po_content(entries: List[Dict[str, Any]], original_content: str) -> str:
    """
    Reconstruct .po file content from parsed entries.
    
    Args:
        entries: Parsed entries with updated translations
        original_content: Original file content for reference
        
    Returns:
        Reconstructed .po file content
    """
    lines = original_content.split('\n')
    result_lines = []
    
    # Track which lines have been processed
    processed_lines = set()
    
    # Separate existing entries from new entries
    existing_entries = [entry for entry in entries if entry['start_line'] < len(lines)]
    new_entries = [entry for entry in entries if entry['start_line'] >= len(lines)]
    
    for entry in existing_entries:
        # Add lines before this entry (if any)
        for line_num in range(len(result_lines), entry['start_line']):
            if line_num < len(lines) and line_num not in processed_lines:
                result_lines.append(lines[line_num])
                processed_lines.add(line_num)
        
        # Add comments
        for comment in entry['comments']:
            result_lines.append(comment)
        
        # Add msgid - preserve original format style
        if 'msgid_lines' in entry and len(entry['msgid_lines']) > 1:
            # Original was multi-line, preserve format but check if content changed
            original_msgid_content = ''.join(_extract_quoted_string(line) for line in entry['msgid_lines'])
            if original_msgid_content == entry['msgid']:
                # Content unchanged, use original lines
                for line in entry['msgid_lines']:
                    result_lines.append(line)
            else:
                # Content changed, format as multi-line to preserve style
                result_lines.extend(_format_multiline_entry('msgid', entry['msgid']))
        elif 'msgid_lines' in entry and len(entry['msgid_lines']) == 1:
            # Original was single-line, preserve format
            escaped_msgid = _escape_po_string(entry['msgid'])
            result_lines.append(f'msgid "{escaped_msgid}"')
        elif 'msgid' in entry:
            # New entry - apply multiline logic only for very long strings or those with newlines
            if entry['msgid'] == "" or '\n' in entry['msgid'] or len(entry['msgid']) > 120:
                result_lines.extend(_format_multiline_entry('msgid', entry['msgid']))
            else:
                escaped_msgid = _escape_po_string(entry['msgid'])
                result_lines.append(f'msgid "{escaped_msgid}"')
        
        # Add msgstr - preserve original format style  
        if 'msgstr_lines' in entry and len(entry['msgstr_lines']) > 1:
            # Original was multi-line, preserve format but check if content changed
            original_msgstr_content = ''.join(_extract_quoted_string(line) for line in entry['msgstr_lines'])
            if original_msgstr_content == entry['msgstr']:
                # Content unchanged, use original lines
                for line in entry['msgstr_lines']:
                    result_lines.append(line)
            else:
                # Content changed, format as multi-line to preserve style
                result_lines.extend(_format_multiline_entry('msgstr', entry['msgstr']))
        elif 'msgstr_lines' in entry and len(entry['msgstr_lines']) == 1:
            # Original was single-line, preserve format
            escaped_msgstr = _escape_po_string(entry['msgstr'])
            result_lines.append(f'msgstr "{escaped_msgstr}"')
        elif 'msgstr' in entry:
            # New entry - apply multiline logic only for very long strings or those with newlines
            if entry['msgstr'] == "" or '\n' in entry['msgstr'] or len(entry['msgstr']) > 120:
                result_lines.extend(_format_multiline_entry('msgstr', entry['msgstr']))
            else:
                escaped_msgstr = _escape_po_string(entry['msgstr'])
                result_lines.append(f'msgstr "{escaped_msgstr}"')
        
        # Add empty line after entry
        result_lines.append('')
        
        # Mark these lines as processed
        for line_num in range(entry['start_line'], entry['end_line'] + 1):
            processed_lines.add(line_num)
    
    # Add any remaining unprocessed lines
    for line_num in range(len(lines)):
        if line_num not in processed_lines:
            result_lines.append(lines[line_num])
    
    # Add new entries at the end
    for entry in new_entries:
        # Add empty line before new entry if the last line isn't empty
        if result_lines and result_lines[-1].strip():
            result_lines.append('')
        
        # Add comments
        for comment in entry['comments']:
            result_lines.append(comment)
        
        # Add msgid - for new entries, be more conservative with multiline
        if entry['msgid'] == "" or '\n' in entry['msgid'] or len(entry['msgid']) > 120:
            result_lines.extend(_format_multiline_entry('msgid', entry['msgid']))
        else:
            escaped_msgid = _escape_po_string(entry['msgid'])
            result_lines.append(f'msgid "{escaped_msgid}"')
        
        # Add msgstr - for new entries, be more conservative with multiline
        if entry['msgstr'] == "" or '\n' in entry['msgstr'] or len(entry['msgstr']) > 120:
            result_lines.extend(_format_multiline_entry('msgstr', entry['msgstr']))
        else:
            escaped_msgstr = _escape_po_string(entry['msgstr'])
            result_lines.append(f'msgstr "{escaped_msgstr}"')
        
        # Add empty line after entry
        result_lines.append('')
    
    return '\n'.join(result_lines)


def _should_be_multiline(text: str) -> bool:
    """
    Determine if a string should be formatted as multi-line in .po format.
    
    Args:
        text: String to check
        
    Returns:
        True if should be multi-line, False otherwise
    """
    # Empty strings or strings with newlines should be multi-line
    # Also format very long strings as multi-line
    return text == "" or '\n' in text or len(text) > 80


def _format_multiline_entry(entry_type: str, text: str) -> List[str]:
    """
    Format a string as a multi-line .po entry.
    
    Args:
        entry_type: 'msgid' or 'msgstr'
        text: Text to format
        
    Returns:
        List of lines for the multi-line entry
    """
    lines = []
    
    if text == "":
        # Empty string - just the entry type with empty quotes
        lines.append(f'{entry_type} ""')
        return lines
    
    # Check if text contains newlines (should be split)
    if '\n' in text:
        # Split on newlines and format each line
        lines.append(f'{entry_type} ""')
        text_lines = text.split('\n')
        for i, line in enumerate(text_lines):
            if i == len(text_lines) - 1 and line == "":
                # Don't add empty line at the end unless it's meaningful
                continue
            escaped_line = _escape_po_string(line + '\n' if i < len(text_lines) - 1 else line)
            lines.append(f'"{escaped_line}"')
    else:
        # Long single line - split at reasonable boundaries
        if len(text) > 80:
            lines.append(f'{entry_type} ""')
            # Simple splitting by words to keep under 80 chars per line
            words = text.split(' ')
            current_line = ""
            for word in words:
                if len(current_line + word + " ") > 75:  # Leave room for quotes and escaping
                    if current_line:
                        escaped_line = _escape_po_string(current_line.rstrip())
                        lines.append(f'"{escaped_line}"')
                        current_line = word + " "
                    else:
                        # Single word longer than limit
                        escaped_line = _escape_po_string(word)
                        lines.append(f'"{escaped_line}"')
                        current_line = ""
                else:
                    current_line += word + " "
            
            if current_line:
                escaped_line = _escape_po_string(current_line.rstrip())
                lines.append(f'"{escaped_line}"')
        else:
            # Short single line - can be on one line
            escaped_text = _escape_po_string(text)
            lines.append(f'{entry_type} "{escaped_text}"')
    
    return lines


def _create_po_from_scratch(content: Dict[str, Any]) -> str:
    """
    Create a .po file from scratch when no template is available.
    
    Args:
        content: Dictionary of translations
        
    Returns:
        Complete .po file content
    """
    lines = []
    
    # Add basic header
    lines.append('# Translation file')
    lines.append('# Generated by algebras-cli')
    lines.append('#')
    lines.append('msgid ""')
    lines.append('msgstr ""')
    lines.append('"Content-Type: text/plain; charset=UTF-8\\n"')
    lines.append('"Content-Transfer-Encoding: 8bit\\n"')
    lines.append('')
    
    # Add all translation entries
    for msgid, msgstr in sorted(content.items()):
        # Skip empty keys
        if not msgid:
            continue
            
        # Add msgid
        if _should_be_multiline(msgid):
            lines.extend(_format_multiline_entry('msgid', msgid))
        else:
            escaped_msgid = _escape_po_string(msgid)
            lines.append(f'msgid "{escaped_msgid}"')
        
        # Add msgstr
        if _should_be_multiline(msgstr):
            lines.extend(_format_multiline_entry('msgstr', msgstr))
        else:
            escaped_msgstr = _escape_po_string(msgstr)
            lines.append(f'msgstr "{escaped_msgstr}"')
        
        lines.append('')  # Empty line between entries
    
    return '\n'.join(lines) 