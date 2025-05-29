import os
import subprocess
import argparse
import sys
from typing import Dict, Optional, Tuple, List, Any
import json
import yaml
import re
import logging
from tqdm import tqdm
from functools import lru_cache

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Create console handler if not already exists
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Cache for git operation results
_git_file_cache = {}
_git_key_cache = {}
_git_blame_cache = {}  # For caching git blame results


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


@lru_cache(maxsize=1024)
def get_key_line_number(file_path: str, key: str) -> Optional[int]:
    """
    Find the line number for a specific key in a translation file.
    Uses LRU cache to avoid redundant lookups.
    
    Args:
        file_path: Path to the file
        key: The key to find (can be nested using dot notation)
        
    Returns:
        Line number where the key is defined or None if not found
    """
    logger.debug(f"\nSearching for key: {key}")
    logger.debug(f"In file: {file_path}")
    
    try:
        # First, check if the file exists
        if not os.path.exists(file_path):
            logger.warning("File not found!")
            return None
            
        # Read the file content to parse the structure
        logger.debug("Reading file content...")
        content = read_file_content(file_path)
        
        # Split the key into parts for nested access
        key_parts = key.split('.')
        logger.debug(f"Split key into parts: {key_parts}")
        
        # For nested structures, we need to find the exact line where the value is defined
        logger.debug("Opening file to read lines...")
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        logger.debug(f"Read {len(lines)} lines from file")
        
        # Different handling based on file format
        if file_path.endswith('.json'):
            # For JSON, we'll traverse the lines looking for the exact key pattern
            logger.debug("Processing JSON file format")
            return _find_json_key_line(lines, key_parts)
        elif file_path.endswith(('.yaml', '.yml')):
            # For YAML, we need to handle indentation
            logger.debug("Processing YAML file format")
            return _find_yaml_key_line(lines, key_parts)
        else:
            logger.warning("Unsupported file format")
            return None
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return None


def _find_json_key_line(lines: List[str], key_parts: List[str]) -> Optional[int]:
    """
    Find the line number for a nested key in a JSON file.
    
    Args:
        lines: File content as a list of lines
        key_parts: Parts of the nested key
        
    Returns:
        Line number where the key is defined or None if not found
    """
    # For better nested key detection, we'll track both nesting level and current path
    current_path = []
    
    # Convert to a more lenient pattern match
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        
        # Skip empty lines
        if not stripped_line:
            continue
        
        # Check if this line contains a key pattern
        if ':' in stripped_line and '"' in stripped_line:
            # Extract the key from the line (between quotes)
            line_parts = stripped_line.split(':', 1)
            if len(line_parts) < 2:
                continue
                
            key_part = line_parts[0].strip()
            
            # Remove quotes
            if key_part.startswith('"') and key_part.endswith('"'):
                key_part = key_part[1:-1]
            
            # Check bracket counts to determine if we're entering or exiting objects
            open_brackets = stripped_line.count('{')
            close_brackets = stripped_line.count('}')
            
            # If we're exiting objects, pop from the path
            if close_brackets > open_brackets:
                # Pop from the path based on number of closing brackets
                for _ in range(close_brackets - open_brackets):
                    if current_path:
                        current_path.pop()
            
            # If we find a key, process it
            if key_part:
                # Check if this key is part of our search path
                if len(current_path) < len(key_parts) and key_part == key_parts[len(current_path)]:
                    current_path.append(key_part)
                    
                    # If we've found all parts of the key, return this line
                    if current_path == key_parts:
                        return i + 1  # Line numbers are 1-indexed
                
                # If we found a different key at this level, update the path
                elif len(current_path) > 0 and current_path[-1] != key_part and key_part in key_parts:
                    # We found a different key at this level
                    current_path = [key_part]
            
            # If we're entering a new object and we're on the right path
            if open_brackets > 0 and not ':' in stripped_line.split('{', 1)[1]:
                # We're entering a new object in the right path
                continue
        
        # Check for closing brackets that might pop our path
        elif '}' in stripped_line:
            count = stripped_line.count('}')
            # Pop from the path based on number of closing brackets
            for _ in range(count):
                if current_path:
                    current_path.pop()
    
    return None


def _find_yaml_key_line(lines: List[str], key_parts: List[str]) -> Optional[int]:
    """
    Find the line number for a nested key in a YAML file.
    
    Args:
        lines: File content as a list of lines
        key_parts: Parts of the nested key
        
    Returns:
        Line number where the key is defined or None if not found
    """
    # YAML uses indentation for nesting
    current_path = []
    current_indent = -1
    
    for i, line in enumerate(lines):
        # Skip empty lines or comments
        if not line.strip() or line.strip().startswith('#'):
            continue
            
        # Calculate the indentation level
        indent = len(line) - len(line.lstrip())
        
        # If we're at a lower indent, pop the path stack
        while current_indent >= 0 and indent <= current_indent:
            current_path.pop()
            current_indent -= 2  # Assuming standard 2-space YAML indentation
        
        # Check if this line contains a key
        stripped = line.strip()
        if ':' in stripped:
            key = stripped.split(':', 1)[0].strip()
            
            # If this key matches our current path level
            if key == key_parts[len(current_path)]:
                current_path.append(key)
                current_indent = indent
                
                # If we've found all parts of the key, return this line
                if current_path == key_parts:
                    return i + 1  # Line numbers are 1-indexed
    
    return None


def get_blame_info_batch(file_path: str, line_numbers: List[int]) -> Dict[int, Tuple[str, str]]:
    """
    Get git blame information for multiple lines in a file with a single git command.
    This is much more efficient than running git blame for each line separately.
    
    Args:
        file_path: Path to the file
        line_numbers: List of line numbers to get blame info for
        
    Returns:
        Dictionary mapping line numbers to tuples of (date, author)
    """
    # Check cache first
    file_key = os.path.abspath(file_path)
    if file_key in _git_blame_cache:
        # Return cached results that match requested line numbers
        cached_results = {ln: _git_blame_cache[file_key].get(ln) 
                         for ln in line_numbers 
                         if ln in _git_blame_cache[file_key]}
        
        # If all line numbers are in cache, return the cached results
        if len(cached_results) == len(line_numbers):
            return cached_results
    else:
        _git_blame_cache[file_key] = {}
        cached_results = {}
    
    # Get the missing line numbers
    missing_lines = [ln for ln in line_numbers if ln not in cached_results]
    if not missing_lines:
        return cached_results
    
    results = {}
    try:
        if not is_git_repository(file_path) or not os.path.exists(file_path):
            return {}
            
        # Get directory and filename separately
        file_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # Use git blame to get information for all requested lines
        # Combine the line ranges to minimize git commands
        line_ranges = []
        current_range = []
        
        # Sort the line numbers to make consecutive range detection easier
        sorted_lines = sorted(missing_lines)
        
        for line in sorted_lines:
            if not current_range or line == current_range[-1] + 1:
                current_range.append(line)
            else:
                line_ranges.append(current_range)
                current_range = [line]
        
        if current_range:
            line_ranges.append(current_range)
        
        # Process each range of consecutive line numbers
        for line_range in line_ranges:
            range_start = line_range[0]
            range_end = line_range[-1]
            
            # Run git blame on the range
            blame_cmd = [
                'git', 'blame', '-L', f'{range_start},{range_end}', 
                '--date=iso', '--', file_name
            ]
            
            result = subprocess.run(
                blame_cmd,
                cwd=file_dir,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                continue
                
            # Parse each line of the blame output
            blame_lines = result.stdout.strip().split('\n')
            for i, blame_line in enumerate(blame_lines):
                line_num = range_start + i
                
                # Extract date and author
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', blame_line)
                author_match = re.search(r'\((.+?)\s+\d{4}-\d{2}-\d{2}', blame_line)
                
                if date_match and author_match:
                    date_str = date_match.group(1)
                    author = author_match.group(1).strip()
                    
                    # Also extract time if available
                    time_match = re.search(r'(\d{2}:\d{2}:\d{2})', blame_line)
                    if time_match:
                        time_str = time_match.group(1)
                        date_str = f"{date_str}T{time_str}Z"
                    
                    results[line_num] = (date_str, author)
                    
                    # Update the cache
                    _git_blame_cache[file_key][line_num] = (date_str, author)
        
        # Combine with cached results
        results.update(cached_results)
        return results
        
    except Exception as e:
        logger.error(f"Error in batch blame operation: {str(e)}")
        return cached_results


@lru_cache(maxsize=1024)
def get_key_last_modification(file_path: str, key: str) -> Optional[str]:
    """
    Get the date when a specific key was last modified in the file using git blame.
    Uses LRU cache to avoid redundant git operations.
    
    Args:
        file_path: Path to the file
        key: The key to check (can be nested using dot notation)
        
    Returns:
        ISO date string of the last modification, or None if not available
    """
    try:
        logger.debug("\nDEBUG - Starting get_key_last_modification")
        if not is_git_repository(file_path) or not os.path.exists(file_path):
            logger.debug(f"DEBUG - Not a git repo or file doesn't exist: {file_path}")
            return None
            
        # Get the line number where the key is defined
        line_number = get_key_line_number(file_path, key)
        if not line_number:
            logger.debug(f"DEBUG - Couldn't find line number for key: {key}")
            return None
        
        logger.debug(f"DEBUG - Found line number: {line_number}")
        
        # Use the batch blame cache if available
        file_key = os.path.abspath(file_path)
        if file_key in _git_blame_cache and line_number in _git_blame_cache[file_key]:
            date_str, _ = _git_blame_cache[file_key][line_number]
            return date_str
            
        # Otherwise, perform the traditional git operations
        # Get directory and filename separately to avoid path duplication
        file_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
            
        # Try git log first (which might be more reliable for getting dates)
        try:
            logger.debug("DEBUG - Trying git log approach first")
            # Use --no-patch to avoid including diff output
            log_result = subprocess.run(
                ['git', 'log', '-1', '--format=%aI', '--no-patch', f'-L{line_number},{line_number}:{file_name}'],
                cwd=file_dir,
                capture_output=True,
                text=True,
                check=False
            )
            
            logger.debug(f"DEBUG - Git log command: git log -1 --format=%aI --no-patch -L{line_number},{line_number}:{file_name}")
            logger.debug(f"DEBUG - Git log return code: {log_result.returncode}")
            logger.debug(f"DEBUG - Git log stdout: {log_result.stdout}")
            logger.debug(f"DEBUG - Git log stderr: {log_result.stderr}")
            
            if log_result.returncode == 0 and log_result.stdout.strip():
                iso_date = log_result.stdout.strip()
                logger.debug(f"DEBUG - Found date using git log: {iso_date}")
                # If it looks like an ISO date, return it
                if len(iso_date) >= 10 and iso_date[4] == '-' and iso_date[7] == '-':
                    # Update the blame cache
                    if file_key not in _git_blame_cache:
                        _git_blame_cache[file_key] = {}
                    _git_blame_cache[file_key][line_number] = (iso_date, "Unknown")
                    return iso_date
        except Exception as e:
            logger.debug(f"DEBUG - Error with git log approach: {str(e)}")
            # Continue to blame approach if log fails
            
        # Use git blame to find who changed this line last
        logger.debug("DEBUG - Trying git blame approach")
        result = subprocess.run(
            ['git', 'blame', '-L', f'{line_number},{line_number}', '--date=iso', file_name],
            cwd=file_dir,
            capture_output=True,
            text=True,
            check=False
        )
        
        logger.debug(f"DEBUG - Git blame command: git blame -L {line_number},{line_number} --date=iso {file_name}")
        logger.debug(f"DEBUG - Git blame return code: {result.returncode}")
        logger.debug(f"DEBUG - Git blame stderr: {result.stderr}")
        
        if result.returncode != 0 or not result.stdout.strip():
            logger.debug(f"DEBUG - Git blame failed with return code: {result.returncode}")
            logger.debug(f"DEBUG - Git blame stderr: {result.stderr}")
            # Fallback to just getting the date
            return get_last_modified_date(file_path)
            
        # Parse the blame output to extract the date
        blame_line = result.stdout.strip()
        logger.debug(f"DEBUG - Blame output: {blame_line}")
        
        # Extract date
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', blame_line)
        time_match = re.search(r'(\d{2}:\d{2}:\d{2})', blame_line)
        
        if date_match and time_match:
            date_str = date_match.group(1)
            time_str = time_match.group(1)
            iso_datetime = f"{date_str}T{time_str}Z"
            logger.debug(f"DEBUG - Extracted date and time: {iso_datetime}")
            
            # Update the blame cache
            if file_key not in _git_blame_cache:
                _git_blame_cache[file_key] = {}
            
            # Extract author information if available
            author_match = re.search(r'\((.+?)\s+\d{4}-\d{2}-\d{2}', blame_line)
            author = author_match.group(1).strip() if author_match else "Unknown"
            
            _git_blame_cache[file_key][line_number] = (iso_datetime, author)
            return iso_datetime
        
        # Fallback to file's last modification date
        logger.debug("DEBUG - Falling back to file's last modification date")
        return get_last_modified_date(file_path)
    except Exception as e:
        logger.error(f"DEBUG - Exception in get_key_last_modification: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


@lru_cache(maxsize=1024)
def compare_key_modifications(source_file: str, target_file: str, key: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Compare the last modification dates of a key between source and target files.
    Uses LRU cache to avoid redundant comparisons.
    
    Args:
        source_file: Path to the source file
        target_file: Path to the target file
        key: The key to compare (can be nested using dot notation)
        
    Returns:
        Tuple containing:
        - Boolean indicating if the target is outdated (True if source is newer)
        - Source file modification date
        - Target file modification date
    """
    source_date = get_key_last_modification(source_file, key)
    target_date = get_key_last_modification(target_file, key)
    
    # If either date is unavailable, we can't determine if it's outdated
    if not source_date or not target_date:
        return False, source_date, target_date
    
    # Compare dates - if source is newer than target, target is outdated
    is_outdated = source_date > target_date
    return is_outdated, source_date, target_date


def test_translation_key_tracking(source_file: str, target_file: str, keys: List[str]) -> Dict:
    """
    Test the key modification tracking logic for a list of translation keys.
    This is useful for debugging or verifying the implementation works as expected.
    
    Args:
        source_file: Path to the source language file (e.g., en.json)
        target_file: Path to the target language file (e.g., ru.json)
        keys: List of keys to check (can be nested using dot notation)
        
    Returns:
        Dictionary with test results for each key
    """
    results = {}
    
    if not (is_git_repository(source_file) and is_git_repository(target_file)):
        return {"error": "One or both paths are not in a Git repository"}
        
    # Check if files exist
    if not os.path.exists(source_file):
        return {"error": f"Source file {source_file} does not exist"}
    if not os.path.exists(target_file):
        return {"error": f"Target file {target_file} does not exist"}
        
    # Test each key with progress bar
    with tqdm(total=len(keys), desc="Testing keys with git") as pbar:
        for key in keys:
            # Get line numbers
            source_line = get_key_line_number(source_file, key)
            target_line = get_key_line_number(target_file, key)
            
            # Get modification info
            source_info = get_key_last_modification(source_file, key)
            target_info = get_key_last_modification(target_file, key)
            
            # Check if outdated
            is_outdated = False
            if source_info and target_info:
                is_outdated = source_info > target_info
                
            # Store results
            results[key] = {
                "source_file": source_file,
                "target_file": target_file,
                "source_line": source_line,
                "target_line": target_line,
                "source_date": source_info,
                "target_date": target_info,
                "is_outdated": is_outdated
            }
            
            pbar.update(1)
        
    return results


def find_outdated_translations(source_file: str, target_file: str) -> Dict[str, Dict]:
    """
    Find all outdated translations by comparing the source and target files.
    This is a high-level utility that does a full comparison of all keys.
    
    Args:
        source_file: Path to the source language file (e.g., en.json)
        target_file: Path to the target language file (e.g., ru.json)
        
    Returns:
        Dictionary of outdated keys with their modification information including:
        - source_date: Last modification date of the key in source file
        - target_date: Last modification date of the key in target file
        - source_commit: Commit hash that last modified the key in source file
        - source_author: Author who last modified the key in source file
        - target_commit: Commit hash that last modified the key in target file
        - target_author: Author who last modified the key in target file
    """
    outdated_keys = {}
    
    # Read both files
    try:
        source_content = read_file_content(source_file)
        target_content = read_file_content(target_file)
    except Exception as e:
        return {"error": f"Failed to read files: {str(e)}"}
        
    # Extract all keys from the source file
    all_keys = _extract_all_keys(source_content)
    
    # Check each key for outdated translations with progress bar
    with tqdm(total=len(all_keys), desc="Checking translations with git") as pbar:
        for key in all_keys:
            source_info = get_key_last_modification(source_file, key)
            target_info = get_key_last_modification(target_file, key)
            
            if not source_info or not target_info:
                pbar.update(1)
                continue
                
            # Compare the dates to see if source is newer than target
            if source_info > target_info:
                outdated_keys[key] = {
                    "source_date": source_info,
                    "target_date": target_info,
                    "source_commit": None,
                    "source_author": None,
                    "target_commit": None,
                    "target_author": None
                }
            
            pbar.update(1)
            
    return outdated_keys


def _extract_all_keys(data: Dict, prefix: str = "", result: List[str] = None) -> List[str]:
    """
    Extract all keys from a nested dictionary, using dot notation for nested keys.
    
    Args:
        data: Dictionary to extract keys from
        prefix: Current key prefix (for recursion)
        result: List to store the keys (for recursion)
        
    Returns:
        List of all keys in dot notation
    """
    if result is None:
        result = []
        
    if not isinstance(data, dict):
        return result
        
    for key, value in data.items():
        current_key = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):
            # Recursively process nested dictionaries
            _extract_all_keys(value, current_key, result)
        else:
            # Add leaf key to the result
            result.append(current_key)
            
    return result


def print_pretty_json(data: Any) -> None:
    """
    Print data as pretty JSON.
    
    Args:
        data: Data to print
    """
    logger.info(json.dumps(data, indent=2, sort_keys=True, default=str))


def show_all_keys(file_path: str) -> List[str]:
    """
    Extract and display all keys from a translation file.
    
    Args:
        file_path: Path to the translation file
        
    Returns:
        List of all keys in the file in dot notation
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return [f"Error: File {file_path} does not exist"]
            
        # Read file content
        content = read_file_content(file_path)
        
        # Extract all keys
        all_keys = _extract_all_keys(content)
        
        return sorted(all_keys)
    except Exception as e:
        return [f"Error: {str(e)}"]


def get_key_commit_info(file_path: str, key: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get the commit SHA and author who last modified a specific key in the file.
    
    Args:
        file_path: Path to the file
        key: The key to check (can be nested using dot notation)
        
    Returns:
        Tuple of (commit_sha, author_name) or (None, None) if not available
    """
    try:
        if not is_git_repository(file_path) or not os.path.exists(file_path):
            return None, None
            
        # Get the line number where the key is defined
        line_number = get_key_line_number(file_path, key)
        if not line_number:
            return None, None
        
        # Get directory and filename separately to avoid path duplication
        file_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
            
        # Use git log to get commit info with --no-patch to avoid diff output
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%H%n%an', '--no-patch', f'-L{line_number},{line_number}:{file_name}'],
            cwd=file_dir,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            return None, None
            
        # Parse the output - first line is commit SHA, second line is author
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 2:
            return lines[0], lines[1]
            
        return None, None
    except Exception as e:
        logger.error(f"Error getting commit info for key: {str(e)}")
        return None, None


def get_keys_last_modifications_batch(file_path: str, keys: List[str]) -> Dict[str, str]:
    """
    Get the dates when multiple keys were last modified in a file using a batch approach.
    
    Args:
        file_path: Path to the file
        keys: List of keys to check
        
    Returns:
        Dictionary mapping keys to their last modification dates
    """
    results = {}
    
    if not keys:
        return results
    
    # Get line numbers for all keys in a single pass
    line_numbers = {}
    for key in keys:
        line_num = get_key_line_number(file_path, key)
        if line_num:
            line_numbers[key] = line_num
    
    if not line_numbers:
        return results
    
    # Get blame info for all line numbers in one batch operation
    blame_info = get_blame_info_batch(file_path, list(line_numbers.values()))
    
    # Map the blame info back to keys
    for key, line_num in line_numbers.items():
        if line_num in blame_info:
            date_str, _ = blame_info[line_num]
            results[key] = date_str
        else:
            # If blame info is missing, try to get it using a fallback method
            # but don't use the slow compare_key_modifications
            try:
                date_str = get_key_last_modification(file_path, key)
                if date_str:
                    results[key] = date_str
            except Exception:
                # If all methods fail, skip this key rather than causing delays
                continue
    
    return results


def main() -> None:
    """
    CLI entry point for the translation key tracking tools.
    """
    # Check if git is available
    if not is_git_available():
        logger.error("Git is not available on your system.")
        sys.exit(1)
    
    # Create the argument parser
    parser = argparse.ArgumentParser(
        description="Translation key tracking tools using Git blame"
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Command to test specific keys
    test_parser = subparsers.add_parser("test", help="Test specific translation keys")
    test_parser.add_argument("source", help="Source language file (e.g., en.json)")
    test_parser.add_argument("target", help="Target language file (e.g., ru.json)")
    test_parser.add_argument("keys", nargs="+", help="Keys to test (dot notation for nested keys)")
    
    # Command to find all outdated keys
    find_parser = subparsers.add_parser("find", help="Find all outdated translation keys")
    find_parser.add_argument("source", help="Source language file (e.g., en.json)")
    find_parser.add_argument("target", help="Target language file (e.g., ru.json)")
    
    # Command to get last modification date for a key
    date_parser = subparsers.add_parser("date", help="Get last modification date for a key")
    date_parser.add_argument("file", help="Language file")
    date_parser.add_argument("key", help="Key to check (dot notation for nested keys)")
    
    # Command to show all keys in a file
    keys_parser = subparsers.add_parser("keys", help="Show all keys in a translation file")
    keys_parser.add_argument("file", help="Language file")
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute the requested command
    try:
        if args.command == "test":
            results = test_translation_key_tracking(args.source, args.target, args.keys)
            print_pretty_json(results)
        
        elif args.command == "find":
            results = find_outdated_translations(args.source, args.target)
            if "error" in results:
                logger.error(f"Error: {results['error']}")
                sys.exit(1)
            
            if not results:
                logger.info("No outdated translations found.")
            else:
                logger.info(f"Found {len(results)} outdated translations:")
                print_pretty_json(results)
        
        elif args.command == "date":
            date = get_key_last_modification(args.file, args.key)
            line = get_key_line_number(args.file, args.key)
            logger.info(f"Key: {args.key}")
            logger.info(f"File: {args.file}")
            logger.info(f"Line: {line}")

            if not date:
                logger.error(f"Could not determine last modification date for key '{args.key}'")
                sys.exit(1)
            
            logger.info(f"Last modified: {date}")
        
        elif args.command == "keys":
            all_keys = show_all_keys(args.file)
            
            if all_keys and all_keys[0].startswith("Error:"):
                logger.error(all_keys[0])
                sys.exit(1)
            
            logger.info(f"Found {len(all_keys)} keys in {args.file}:")
            for key in all_keys:
                logger.info(f"- {key}")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 