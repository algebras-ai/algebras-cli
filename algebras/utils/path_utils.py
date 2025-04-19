import os

def determine_target_path(source_path: str, source_lang: str, target_lang: str) -> str:
    """
    Determine the target file path by replacing the source language folder with target language folder.
    
    Args:
        source_path: The source file path
        source_lang: Source language code
        target_lang: Target language code
        
    Returns:
        Target file path
    """
    # Replace the source language folder with target language folder if present
    target_path = source_path
    
    # Handle path separators for different operating systems
    if f"/{source_lang}/" in source_path or f"\\{source_lang}\\" in source_path:
        target_path = source_path.replace(f"/{source_lang}/", f"/{target_lang}/")
        target_path = target_path.replace(f"\\{source_lang}\\", f"\\{target_lang}\\")
    elif source_path.endswith(f"/{source_lang}") or source_path.endswith(f"\\{source_lang}"):
        target_path = source_path[:-len(source_lang)] + target_lang
    
    return target_path 