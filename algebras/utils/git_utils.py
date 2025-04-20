import os
import subprocess
from typing import Dict, Optional, Tuple, List
import json
import yaml


def is_git_available() -> bool:
    """
    Check if git is available on the system.
    
    Returns:
        True if git is available, False otherwise
    """
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def is_git_repository(path: str) -> bool:
    """
    Check if the given path is within a git repository.
    
    Args:
        path: Path to check
        
    Returns:
        True if path is in a git repository, False otherwise
    """
    try:
        # Go to the directory containing the file
        file_dir = os.path.dirname(path) if os.path.isfile(path) else path
        
        # Check if this is a git repository
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=file_dir,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0 and result.stdout.strip() == 'true'
    except Exception:
        return False


def get_last_modified_date(file_path: str) -> Optional[str]:
    """
    Get the date of the last commit that modified the file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        ISO date string of the last modification or None if not available
    """
    try:
        if not is_git_repository(file_path):
            return None
            
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%aI', '--', file_path],
            cwd=os.path.dirname(file_path),
            capture_output=True,
            text=True,
            check=True
        )
        date = result.stdout.strip()
        return date if date else None
    except Exception:
        return None


def read_file_content(file_path: str) -> Dict:
    """
    Read a language file and return its contents as a dictionary.
    
    Args:
        file_path: Path to the language file
        
    Returns:
        Dictionary containing the file contents
    """
    if file_path.endswith('.json'):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif file_path.endswith(('.yaml', '.yml')):
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    else:
        raise ValueError(f"Unsupported file format: {file_path}")


def get_key_last_modification(file_path: str, key: str) -> Optional[str]:
    """
    Get the date when a specific key was last modified in the file.
    
    Args:
        file_path: Path to the file
        key: The key to check (can be nested using dot notation)
        
    Returns:
        ISO date string of the last modification or None if not available
    """
    try:
        if not is_git_repository(file_path):
            return None
            
        key_parts = key.split('.')
        
        # Construct a grep pattern for the key
        # This simplified approach works for most JSON/YAML files
        # but might not be 100% accurate for all formats and structures
        grep_pattern = '\\b' + '\\b.*\\b'.join([part for part in key_parts]) + '\\b'
        
        # Use git log with grep to find commits that modified the key
        result = subprocess.run(
            ['git', 'log', '--format=%aI', '-p', '--', file_path, '|', 'grep', '-E', grep_pattern, '|', 'head', '-n', '1'],
            cwd=os.path.dirname(file_path),
            capture_output=True,
            text=True,
            check=False,
            shell=True
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            # If grep didn't find anything, fall back to the file's last modification date
            return get_last_modified_date(file_path)
            
        # Try to find the last commit date with a different approach
        result = subprocess.run(
            ['git', 'log', '--format=%aI', '-G', grep_pattern, '--', file_path],
            cwd=os.path.dirname(file_path),
            capture_output=True,
            text=True,
            check=False
        )
        
        date_lines = result.stdout.strip().split('\n')
        return date_lines[0] if date_lines else None
    except Exception:
        return None


def compare_key_modifications(source_file: str, target_file: str, key: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Compare when a key was last modified in source and target files.
    
    Args:
        source_file: Path to the source language file
        target_file: Path to the target language file
        key: The key to compare
        
    Returns:
        Tuple of (is_outdated, source_date, target_date)
        is_outdated is True if the source file key is more recent than the target file key
    """
    source_date = get_key_last_modification(source_file, key)
    target_date = get_key_last_modification(target_file, key)
    
    # If we couldn't get the dates, we can't determine if it's outdated
    if not source_date or not target_date:
        return False, source_date, target_date
        
    # Compare the dates to see if source is newer than target
    return source_date > target_date, source_date, target_date 