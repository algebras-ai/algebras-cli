"""
JavaScript/TypeScript parser utility for detecting hardcoded strings
"""

import os
import json
import subprocess
import shutil
from typing import List, Dict, Any, Optional, Tuple


def check_nodejs_available() -> bool:
    """Check if Node.js is available on the system."""
    return shutil.which('node') is not None


def check_dependencies_installed() -> bool:
    """Check if Node.js dependencies are installed."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    package_json = os.path.join(script_dir, 'package.json')
    node_modules = os.path.join(script_dir, 'node_modules')
    
    if not os.path.exists(package_json):
        return False
    
    # Check if @swc/core is installed
    swc_path = os.path.join(node_modules, '@swc', 'core')
    return os.path.exists(swc_path)


def parse_files(input_patterns: List[str], ignore_patterns: Optional[List[str]] = None, 
                config: Optional[Dict[str, Any]] = None, verbose: bool = False) -> Tuple[bool, str, Dict[str, List[Dict[str, Any]]]]:
    """
    Parse JavaScript/TypeScript files to find hardcoded strings.
    
    Args:
        input_patterns: List of glob patterns for source files (e.g., ['src/**/*.{js,jsx,ts,tsx}'])
        ignore_patterns: List of ignore patterns (e.g., ['node_modules/**'])
        config: Configuration dict with extract settings (transComponents, ignoredTags, ignoredAttributes)
        
    Returns:
        Tuple of (success: bool, message: str, files: Dict[str, List[Dict[str, Any]]])
        files dict maps file paths to lists of issues, each issue has 'text' and 'line' keys
    """
    if not check_nodejs_available():
        return False, "Node.js is not available. Please install Node.js to use the parse command.", {}
    
    if not check_dependencies_installed():
        return False, "Node.js dependencies are not installed. Run 'npm install' in algebras/utils/ directory.", {}
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser_script = os.path.join(script_dir, 'js_parser.js')
    
    if not os.path.exists(parser_script):
        return False, f"Parser script not found at {parser_script}", {}
    
    # Get the current working directory (where the user ran the command)
    # This ensures glob patterns work relative to the project root
    project_root = os.getcwd()
    
    # Prepare arguments
    input_patterns_json = json.dumps(input_patterns)
    ignore_patterns_json = json.dumps(ignore_patterns or [])
    config_json = json.dumps(config or {'extract': {}})
    
    try:
        # Call Node.js script from project root so glob patterns work correctly
        # Use absolute path to the script so it can be found from any directory
        result = subprocess.run(
            ['node', parser_script, input_patterns_json, ignore_patterns_json, config_json],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        # Debug: print stderr if there's any output (contains debug messages)
        if result.stderr and verbose:
            # Parse debug messages from stderr (they're JSON formatted)
            import sys
            for line in result.stderr.strip().split('\n'):
                line = line.strip()
                if line:
                    try:
                        debug_data = json.loads(line)
                        if 'debug' in debug_data:
                            print(f"DEBUG: {debug_data['debug']}", file=sys.stderr)
                    except:
                        pass  # Not JSON, ignore
        
        if result.returncode != 0:
            # Try to parse error output
            try:
                error_data = json.loads(result.stderr.strip() or result.stdout.strip())
                error_msg = error_data.get('error', result.stderr or result.stdout)
            except:
                error_msg = result.stderr or result.stdout or "Unknown error"
            return False, f"Parser error: {error_msg}", {}
        
        # Parse JSON output
        output = result.stdout.strip()
        if not output:
            return False, "Parser returned no output", {}
        
        # Handle multiple JSON objects (if errors were printed before the result)
        lines = output.split('\n')
        result_line = None
        for line in reversed(lines):
            line = line.strip()
            if line and line.startswith('{'):
                try:
                    result_line = json.loads(line)
                    break
                except:
                    continue
        
        if result_line is None:
            return False, f"Failed to parse parser output: {output}", {}
        
        if 'error' in result_line:
            return False, f"Parser error: {result_line['error']}", {}
        
        success = result_line.get('success', False)
        message = result_line.get('message', '')
        files = result_line.get('files', {})
        
        return success, message, files
        
    except subprocess.TimeoutExpired:
        return False, "Parser timed out after 5 minutes", {}
    except json.JSONDecodeError as e:
        return False, f"Failed to parse parser output as JSON: {str(e)}", {}
    except Exception as e:
        return False, f"Error running parser: {str(e)}", {}

