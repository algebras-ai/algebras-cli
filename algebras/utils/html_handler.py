"""
HTML file handler for reading and writing HTML translation files using BeautifulSoup4
"""

import hashlib
from typing import Dict, List, Tuple, Set
from bs4 import BeautifulSoup, NavigableString, Tag


def read_html_file(file_path: str) -> Dict[str, str]:
    """
    Read an HTML file and extract translatable text with unique keys.
    
    Args:
        file_path: Path to the HTML file
        
    Returns:
        Dictionary mapping content hash keys to translatable text
    """
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    
    # Remove style and script tags completely
    for tag in soup(["style", "script"]):
        tag.decompose()
    
    translations = {}
    
    # Extract text content from tags
    text_tags = [
        "p", "span", "div", "td", "th", "li", "a", "h1", "h2", "h3", "h4", "h5", "h6",
        "button", "label", "strong", "em", "b", "i", "u", "small", "big", "caption",
        "title", "option", "textarea", "legend", "figcaption", "summary", "details"
    ]
    
    for tag_name in text_tags:
        for tag in soup.find_all(tag_name):
            # Extract individual text nodes to handle mixed content properly
            text_nodes = []
            for content in tag.contents:
                if isinstance(content, NavigableString):
                    text_content = str(content).strip()
                    if text_content:
                        text_nodes.append(text_content)
            
            # If we have text nodes, process each one
            if text_nodes:
                for text in text_nodes:
                    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:12]
                    translations[text_hash] = text
            else:
                # Fallback to get_text for simple cases
                text = tag.get_text(strip=True)
                if text:
                    # Create hash key for the text content
                    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:12]
                    translations[text_hash] = text
    
    # Extract alt attributes from images
    for img in soup.find_all("img"):
        alt_text = img.get("alt", "").strip()
        if alt_text:
            text_hash = hashlib.md5(alt_text.encode('utf-8')).hexdigest()[:12]
            translations[text_hash] = alt_text
    
    # Extract title attributes from elements that have them
    for element in soup.find_all(attrs={"title": True}):
        title_text = element.get("title", "").strip()
        if title_text:
            text_hash = hashlib.md5(title_text.encode('utf-8')).hexdigest()[:12]
            translations[text_hash] = title_text
    
    # Extract placeholder attributes from input elements
    for element in soup.find_all(["input", "textarea"], attrs={"placeholder": True}):
        placeholder_text = element.get("placeholder", "").strip()
        if placeholder_text:
            text_hash = hashlib.md5(placeholder_text.encode('utf-8')).hexdigest()[:12]
            translations[text_hash] = placeholder_text
    
    return translations


def write_html_file(file_path: str, original_file_path: str, translations: Dict[str, str]) -> None:
    """
    Write translated HTML file by replacing original text with translations.
    
    Args:
        file_path: Path where to save the translated HTML file
        original_file_path: Path to the original HTML file (template)
        translations: Dictionary mapping content hash keys to translated text
    """
    with open(original_file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    
    # Remove style and script tags completely (they shouldn't be translated)
    for tag in soup(["style", "script"]):
        tag.decompose()
    
    # Create reverse mapping from original text to translation
    original_to_translation = {}
    
    # First pass: build mapping from original text to translations
    with open(original_file_path, "r", encoding="utf-8") as f:
        original_soup = BeautifulSoup(f, "html.parser")
    
    # Remove style and script tags from original
    for tag in original_soup(["style", "script"]):
        tag.decompose()
    
    original_translations = read_html_file(original_file_path)
    for text_hash, original_text in original_translations.items():
        if text_hash in translations:
            original_to_translation[original_text] = translations[text_hash]
    
    # Replace text content in tags
    text_tags = [
        "p", "span", "div", "td", "th", "li", "a", "h1", "h2", "h3", "h4", "h5", "h6",
        "button", "label", "strong", "em", "b", "i", "u", "small", "big", "caption",
        "title", "option", "textarea", "legend", "figcaption", "summary", "details"
    ]
    
    for tag_name in text_tags:
        for tag in soup.find_all(tag_name):
            # Handle tags with mixed content (text + other tags) - process all NavigableString content
            for content in list(tag.contents):  # Use list() to avoid modification during iteration
                if isinstance(content, NavigableString):
                    text_content = str(content).strip()
                    if text_content and text_content in original_to_translation:
                        content.replace_with(original_to_translation[text_content])
    
    # Replace alt attributes in images
    for img in soup.find_all("img"):
        alt_text = img.get("alt", "").strip()
        if alt_text and alt_text in original_to_translation:
            img["alt"] = original_to_translation[alt_text]
    
    # Replace title attributes
    for element in soup.find_all(attrs={"title": True}):
        title_text = element.get("title", "").strip()
        if title_text and title_text in original_to_translation:
            element["title"] = original_to_translation[title_text]
    
    # Replace placeholder attributes
    for element in soup.find_all(["input", "textarea"], attrs={"placeholder": True}):
        placeholder_text = element.get("placeholder", "").strip()
        if placeholder_text and placeholder_text in original_to_translation:
            element["placeholder"] = original_to_translation[placeholder_text]
    
    # Write the translated HTML file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(str(soup))


def get_html_element_locations(file_path: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Get locations of each translatable text in the HTML file for proper replacement.
    
    Args:
        file_path: Path to the HTML file
        
    Returns:
        Dictionary mapping text hash to list of (element_type, context) tuples
    """
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    
    # Remove style and script tags
    for tag in soup(["style", "script"]):
        tag.decompose()
    
    element_locations = {}
    
    # Track text content locations
    text_tags = [
        "p", "span", "div", "td", "th", "li", "a", "h1", "h2", "h3", "h4", "h5", "h6",
        "button", "label", "strong", "em", "b", "i", "u", "small", "big", "caption",
        "title", "option", "textarea", "legend", "figcaption", "summary", "details"
    ]
    
    for tag_name in text_tags:
        for idx, tag in enumerate(soup.find_all(tag_name)):
            # Extract individual text nodes to handle mixed content properly
            text_nodes = []
            for content in tag.contents:
                if isinstance(content, NavigableString):
                    text_content = str(content).strip()
                    if text_content:
                        text_nodes.append(text_content)
            
            # If we have text nodes, process each one
            if text_nodes:
                for text in text_nodes:
                    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:12]
                    if text_hash not in element_locations:
                        element_locations[text_hash] = []
                    
                    # Create context information
                    classes = tag.get("class", [])
                    class_str = ".".join(classes) if classes else ""
                    context = f"{tag_name}[{idx}]" + (f".{class_str}" if class_str else "")
                    element_locations[text_hash].append(("text_content", context))
            else:
                # Fallback to get_text for simple cases
                text = tag.get_text(strip=True)
                if text:
                    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:12]
                    if text_hash not in element_locations:
                        element_locations[text_hash] = []
                    
                    # Create context information
                    classes = tag.get("class", [])
                    class_str = ".".join(classes) if classes else ""
                    context = f"{tag_name}[{idx}]" + (f".{class_str}" if class_str else "")
                    element_locations[text_hash].append(("text_content", context))
    
    # Track alt attribute locations
    for idx, img in enumerate(soup.find_all("img")):
        alt_text = img.get("alt", "").strip()
        if alt_text:
            text_hash = hashlib.md5(alt_text.encode('utf-8')).hexdigest()[:12]
            if text_hash not in element_locations:
                element_locations[text_hash] = []
            element_locations[text_hash].append(("alt_attribute", f"img[{idx}]"))
    
    # Track title attribute locations
    for idx, element in enumerate(soup.find_all(attrs={"title": True})):
        title_text = element.get("title", "").strip()
        if title_text:
            text_hash = hashlib.md5(title_text.encode('utf-8')).hexdigest()[:12]
            if text_hash not in element_locations:
                element_locations[text_hash] = []
            element_locations[text_hash].append(("title_attribute", f"{element.name}[{idx}]"))
    
    # Track placeholder attribute locations
    for idx, element in enumerate(soup.find_all(["input", "textarea"], attrs={"placeholder": True})):
        placeholder_text = element.get("placeholder", "").strip()
        if placeholder_text:
            text_hash = hashlib.md5(placeholder_text.encode('utf-8')).hexdigest()[:12]
            if text_hash not in element_locations:
                element_locations[text_hash] = []
            element_locations[text_hash].append(("placeholder_attribute", f"{element.name}[{idx}]"))
    
    return element_locations
