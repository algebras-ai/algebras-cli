#!/usr/bin/env python3
"""
po_merger.py

A utility script for processing GNU gettext Portable Object (.po) files by merging multi-line msgid and msgstr entries
into single-line equivalents. This is particularly useful for localization workflows where line-wrapped PO entries,
often introduced by editors or tooling, can cause confusion, complicate diffs, or interfere with downstream processing.

Features:
---------
- Scans a specified directory recursively for all .po files.
- For each .po file found, reformats every msgid or msgstr that is split across multiple quoted lines into a 
  single-line form (preserving all content and escape sequences), except for the file-header entry which is preserved as is.
- Automatically applies proper escaping for embedded quotes, newlines, carriage returns, and tabs to maintain
  PO file compatibility.
- Only rewrites a file if changes are actually performed, preserving file modification times otherwise.

Intended Usage:
---------------
- Run this script after bulk-editing PO files, after hand-edits, or before diffing to reduce spurious spacing changes.
- This script is safe for idempotent use – running multiple times causes no further modification after the first pass.

Example:
--------
Before:
    msgid ""
    "Multi-line "
    "identifier"
    msgstr ""
    "Valor multi-\n"
    "línea"

After:
    msgid "Multi-line identifier"
    msgstr "Valor multi-\nlínea"

Command Line Interface:
-----------------------
- Run this script after bulk-editing PO files, after hand-edits, or before diffing to reduce spurious spacing changes.


Author:
-------
Dima Pukhov from Algebras AI, 2025 (adapted for custom workflow).

"""

import argparse
import os
from pathlib import Path


def find_po_files(directory: str) -> list:
    """
    Recursively find all .po files in the given directory.
    
    Args:
        directory: Root directory to search
        
    Returns:
        List of paths to .po files
    """
    po_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.po'):
                po_files.append(os.path.join(root, file))
    return sorted(po_files)


def extract_quoted_string(line: str) -> str:
    """
    Extract string content from a quoted line in PO format.
    
    Args:
        line: Line containing quoted string (e.g., '"text\\n"')
        
    Returns:
        Unescaped string content
    """
    # Remove leading/trailing whitespace and quotes
    line = line.strip()
    if line.startswith('"') and line.endswith('"'):
        content = line[1:-1]
        # Unescape common sequences (order matters - backslash first)
        content = content.replace('\\\\', '\\')
        content = content.replace('\\"', '"')
        content = content.replace('\\n', '\n')
        content = content.replace('\\r', '\r')
        content = content.replace('\\t', '\t')
        return content
    return ''


def escape_po_string(text: str) -> str:
    """
    Escape text for .po string format.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text
    """
    # Order matters - backslash first
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    text = text.replace('\n', '\\n')
    text = text.replace('\r', '\\r')
    text = text.replace('\t', '\\t')
    return text


def merge_po_file(file_path: str) -> bool:
    """
    Merge multi-line msgid and msgstr entries in a PO file.
    
    Args:
        file_path: Path to the PO file
        
    Returns:
        True if file was modified, False otherwise
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    output_lines = []
    i = 0
    modified = False
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check if this is a msgid "" or msgstr "" that might be multi-line
        if stripped == 'msgid ""' or stripped.startswith('msgid ""'):
            # Collect the msgid entry
            msgid_lines = [line]
            i += 1
            
            # Collect all continuation lines (lines starting with ")
            msgid_content_parts = []
            while i < len(lines) and lines[i].strip().startswith('"'):
                msgid_lines.append(lines[i])
                content = extract_quoted_string(lines[i])
                msgid_content_parts.append(content)
                i += 1
            
            # Check if msgid is empty (header entry) - skip processing if so
            merged_msgid_content = ''.join(msgid_content_parts)
            if not merged_msgid_content.strip():
                # Empty msgid (header entry), keep as is and don't process
                output_lines.extend(msgid_lines)
                
                # Also keep the msgstr as-is if it follows
                if i < len(lines):
                    next_line = lines[i].strip()
                    if next_line == 'msgstr ""' or next_line.startswith('msgstr ""'):
                        msgstr_lines = [lines[i]]
                        i += 1
                        while i < len(lines) and lines[i].strip().startswith('"'):
                            msgstr_lines.append(lines[i])
                            i += 1
                        output_lines.extend(msgstr_lines)
                    elif next_line.startswith('msgstr "'):
                        # Single-line msgstr, keep as is
                        output_lines.append(lines[i])
                        i += 1
                continue
            
            # Non-empty msgid - process and merge
            if len(msgid_content_parts) > 0:
                escaped_content = escape_po_string(merged_msgid_content)
                output_lines.append(f'msgid "{escaped_content}"\n')
                modified = True
            else:
                # Single line msgid "", keep as is
                output_lines.extend(msgid_lines)
            
            # Now check for msgstr that follows immediately
            if i < len(lines):
                next_line = lines[i].strip()
                # Check for msgstr "" with continuation lines
                if next_line == 'msgstr ""' or next_line.startswith('msgstr ""'):
                    # Collect the msgstr entry
                    msgstr_lines = [lines[i]]
                    i += 1
                    
                    # Collect all continuation lines
                    msgstr_content_parts = []
                    while i < len(lines) and lines[i].strip().startswith('"'):
                        msgstr_lines.append(lines[i])
                        content = extract_quoted_string(lines[i])
                        msgstr_content_parts.append(content)
                        i += 1
                    
                    # If we have multiple lines, merge them
                    if len(msgstr_content_parts) > 0:
                        merged_content = ''.join(msgstr_content_parts)
                        escaped_content = escape_po_string(merged_content)
                        output_lines.append(f'msgstr "{escaped_content}"\n')
                        modified = True
                    else:
                        # Single line msgstr "", keep as is
                        output_lines.extend(msgstr_lines)
                    continue  # Continue only if we processed msgstr
                # Check for single-line msgstr "..." (not starting with msgstr "")
                elif next_line.startswith('msgstr "'):
                    # Single-line msgstr, keep as is
                    output_lines.append(lines[i])
                    i += 1
                    continue
        
        # Check for msgstr "" that's not immediately after msgid
        elif stripped == 'msgstr ""' or stripped.startswith('msgstr ""'):
            # Collect the msgstr entry
            msgstr_lines = [line]
            i += 1
            
            # Collect all continuation lines
            msgstr_content_parts = []
            while i < len(lines) and lines[i].strip().startswith('"'):
                msgstr_lines.append(lines[i])
                content = extract_quoted_string(lines[i])
                msgstr_content_parts.append(content)
                i += 1
            
            # If we have multiple lines, merge them
            if len(msgstr_content_parts) > 0:
                merged_content = ''.join(msgstr_content_parts)
                escaped_content = escape_po_string(merged_content)
                output_lines.append(f'msgstr "{escaped_content}"\n')
                modified = True
            else:
                # Single line msgstr "", keep as is
                output_lines.extend(msgstr_lines)
            continue
        
        # Regular line, keep as is
        output_lines.append(line)
        i += 1
    
    # Write back if modified
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(output_lines)
    
    return modified


def main():
    """Main function to process all PO files."""
    parser = argparse.ArgumentParser(
        description='Merge multi-line msgid and msgstr entries in PO files into single lines.'
    )
    parser.add_argument(
        'folder',
        type=str,
        help='Path to the folder containing PO files to process'
    )
    
    args = parser.parse_args()
    data_dir = Path(args.folder)
    
    if not data_dir.exists():
        print(f"Error: Directory {data_dir} does not exist")
        return
    
    if not data_dir.is_dir():
        print(f"Error: {data_dir} is not a directory")
        return
    
    po_files = find_po_files(str(data_dir))
    
    if not po_files:
        print(f"No PO files found in {data_dir}")
        return
    
    print(f"Found {len(po_files)} PO file(s)")
    
    modified_count = 0
    for po_file in po_files:
        print(f"Processing: {po_file}")
        if merge_po_file(po_file):
            modified_count += 1
            print(f"  ✓ Modified")
        else:
            print(f"  - No changes needed")
    
    print(f"\nCompleted: {modified_count} file(s) modified out of {len(po_files)} total")


if __name__ == '__main__':
    main()

