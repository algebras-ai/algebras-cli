"""
Translation validation module for healthcheck command
Validates translation quality across all supported formats
"""

import re
from typing import List, Dict, Tuple, Set, Optional
from html.parser import HTMLParser


class Issue:
    """Represents a validation issue"""
    def __init__(self, severity: str, category: str, message: str, key: Optional[str] = None):
        self.severity = severity  # 'error' or 'warning'
        self.category = category  # 'formatting', 'placeholders', 'numbers', 'html_xml', 'tokens'
        self.message = message
        self.key = key


def check_formatting(source: str, target: str, key: Optional[str] = None) -> List[Issue]:
    """
    Check formatting issues: escape sequences, leading/trailing spaces.
    
    Args:
        source: Source string
        target: Target translation string
        key: Optional key for context
        
    Returns:
        List of formatting issues
    """
    issues = []
    
    # Check newline consistency
    source_has_newline = '\n' in source or '\\n' in source
    target_has_newline = '\n' in target or '\\n' in target
    if source_has_newline and not target_has_newline:
        issues.append(Issue('error', 'formatting', 
            'Source contains newline (\\n) but translation does not', key))
    elif not source_has_newline and target_has_newline:
        issues.append(Issue('warning', 'formatting',
            'Translation contains newline (\\n) but source does not', key))
    
    # Check escape sequences
    escape_sequences = ['\\t', '\\"', '\\\\', '\\r']
    for esc in escape_sequences:
        source_count = source.count(esc)
        target_count = target.count(esc)
        if source_count != target_count:
            issues.append(Issue('warning', 'formatting',
                f'Escape sequence {esc} count mismatch: source has {source_count}, translation has {target_count}', key))
    
    # Check leading/trailing spaces
    source_leading = len(source) - len(source.lstrip())
    source_trailing = len(source) - len(source.rstrip())
    target_leading = len(target) - len(target.lstrip())
    target_trailing = len(target) - len(target.rstrip())
    
    if source_leading != target_leading:
        issues.append(Issue('error', 'formatting',
            f'Leading space mismatch: source has {source_leading}, translation has {target_leading}', key))
    if source_trailing != target_trailing:
        issues.append(Issue('error', 'formatting',
            f'Trailing space mismatch: source has {source_trailing}, translation has {target_trailing}', key))
    
    return issues


def extract_placeholders(text: str) -> Dict[str, List[str]]:
    """
    Extract all placeholders from a string.
    
    Returns:
        Dictionary with keys: 'printf', 'python', 'qt', 'icu', 'other'
    """
    placeholders = {
        'printf': [],
        'python': [],
        'qt': [],
        'icu': [],
        'other': []
    }
    
    # Printf placeholders: %s, %d, %f, %1$s, %02d, etc.
    # Pattern: %[flags][width][.precision][length]specifier or %[position]$[flags][width][.precision][length]specifier
    printf_pattern = r'%(\d+\$)?[0-9]*\.?[0-9]*[sdioxXucfFeEgGaAnp%]'
    for match in re.finditer(printf_pattern, text):
        placeholder = match.group(0)
        if placeholder != '%%':  # Skip escaped %
            placeholders['printf'].append(placeholder)
    
    # Python placeholders: %(name)s, %(name)d, etc.
    python_pattern = r'%\([^)]+\)[sdioxXucfFeEgGaAn]'
    for match in re.finditer(python_pattern, text):
        placeholders['python'].append(match.group(0))
    
    # Qt placeholders: %1, %2, %3, etc.
    qt_pattern = r'%[0-9]+'
    for match in re.finditer(qt_pattern, text):
        placeholders['qt'].append(match.group(0))
    
    # ICU placeholders: {variable}, {count, plural, ...}, etc.
    # This is more complex, need to handle nested braces
    icu_pattern = r'\{[^}]*\}'
    brace_depth = 0
    current_icu = ''
    i = 0
    while i < len(text):
        if text[i] == '{':
            if brace_depth == 0:
                current_icu = '{'
            else:
                current_icu += '{'
            brace_depth += 1
        elif text[i] == '}':
            current_icu += '}'
            brace_depth -= 1
            if brace_depth == 0:
                placeholders['icu'].append(current_icu)
                current_icu = ''
        else:
            if brace_depth > 0:
                current_icu += text[i]
        i += 1
    
    # Other common patterns: {variable}, {0}, $variable, ${variable}, @name, {{mustache}}
    # Simple braces (not ICU plural)
    simple_brace_pattern = r'\{[a-zA-Z_][a-zA-Z0-9_]*\}'
    for match in re.finditer(simple_brace_pattern, text):
        placeholder = match.group(0)
        # Skip if already captured as ICU
        if not any(placeholder in icu for icu in placeholders['icu']):
            placeholders['other'].append(placeholder)
    
    # Mustache double braces
    mustache_pattern = r'\{\{[^}]+\}\}'
    for match in re.finditer(mustache_pattern, text):
        placeholders['other'].append(match.group(0))
    
    # Variable patterns: $variable, ${variable}
    var_pattern = r'\$\{?[a-zA-Z_][a-zA-Z0-9_]*\}?'
    for match in re.finditer(var_pattern, text):
        placeholders['other'].append(match.group(0))
    
    # @name patterns
    at_pattern = r'@[a-zA-Z_][a-zA-Z0-9_]*'
    for match in re.finditer(at_pattern, text):
        placeholders['other'].append(match.group(0))
    
    return placeholders


def check_placeholders(source: str, target: str, key: Optional[str] = None) -> List[Issue]:
    """
    Check placeholder consistency between source and target.
    
    Args:
        source: Source string
        target: Target translation string
        key: Optional key for context
        
    Returns:
        List of placeholder issues
    """
    issues = []
    
    source_placeholders = extract_placeholders(source)
    target_placeholders = extract_placeholders(target)
    
    # Check each placeholder type
    for ptype in ['printf', 'python', 'qt', 'icu', 'other']:
        source_pl = source_placeholders[ptype]
        target_pl = target_placeholders[ptype]
        
        # Count occurrences
        source_counts = {}
        for pl in source_pl:
            source_counts[pl] = source_counts.get(pl, 0) + 1
        
        target_counts = {}
        for pl in target_pl:
            target_counts[pl] = target_counts.get(pl, 0) + 1
        
        # Check for missing placeholders
        for pl, count in source_counts.items():
            if pl not in target_counts:
                issues.append(Issue('error', 'placeholders',
                    f'Missing placeholder in translation: {pl} (appears {count} time(s) in source)', key))
            elif target_counts[pl] < count:
                issues.append(Issue('error', 'placeholders',
                    f'Placeholder {pl} appears {count} time(s) in source but only {target_counts[pl]} time(s) in translation', key))
        
        # Check for extra placeholders
        for pl, count in target_counts.items():
            if pl not in source_counts:
                issues.append(Issue('warning', 'placeholders',
                    f'Extra placeholder in translation: {pl} (not in source)', key))
            elif source_counts[pl] < count:
                issues.append(Issue('warning', 'placeholders',
                    f'Placeholder {pl} appears {count} time(s) in translation but only {source_counts[pl]} time(s) in source', key))
        
        # For printf, check type consistency
        if ptype == 'printf':
            for pl in source_pl:
                if pl in target_pl:
                    # Extract specifier (last character)
                    source_spec = pl[-1] if len(pl) > 0 else ''
                    # Find matching placeholder in target
                    target_matches = [tpl for tpl in target_pl if tpl == pl]
                    if target_matches:
                        target_spec = target_matches[0][-1] if len(target_matches[0]) > 0 else ''
                        # Check if specifier type changed (some changes are acceptable, some are not)
                        numeric_specs = {'d', 'i', 'o', 'x', 'X', 'u'}
                        string_specs = {'s', 'c'}
                        if source_spec in numeric_specs and target_spec in string_specs:
                            issues.append(Issue('error', 'placeholders',
                                f'Placeholder type changed from numeric ({source_spec}) to string ({target_spec}): {pl}', key))
                        elif source_spec in string_specs and target_spec in numeric_specs:
                            issues.append(Issue('error', 'placeholders',
                                f'Placeholder type changed from string ({source_spec}) to numeric ({target_spec}): {pl}', key))
    
    return issues


def check_numbers(source: str, target: str, key: Optional[str] = None) -> List[Issue]:
    """
    Check numeric values consistency.
    
    Args:
        source: Source string
        target: Target translation string
        key: Optional key for context
        
    Returns:
        List of number-related issues
    """
    issues = []
    
    # Extract numbers (integers and floats)
    number_pattern = r'\b\d+\.?\d*\b'
    source_numbers = re.findall(number_pattern, source)
    target_numbers = re.findall(number_pattern, target)
    
    # Compare numbers
    if len(source_numbers) != len(target_numbers):
        issues.append(Issue('warning', 'numbers',
            f'Number count mismatch: source has {len(source_numbers)} number(s), translation has {len(target_numbers)}', key))
    else:
        # Check if numbers match
        for i, (src_num, tgt_num) in enumerate(zip(source_numbers, target_numbers)):
            # Normalize (remove leading zeros, compare as floats if decimal)
            try:
                src_val = float(src_num)
                tgt_val = float(tgt_num)
                if src_val != tgt_val:
                    issues.append(Issue('error', 'numbers',
                        f'Number mismatch at position {i+1}: source has {src_num}, translation has {tgt_num}', key))
            except ValueError:
                # If can't parse as number, just compare strings
                if src_num != tgt_num:
                    issues.append(Issue('warning', 'numbers',
                        f'Number format mismatch at position {i+1}: source has {src_num}, translation has {tgt_num}', key))
    
    return issues


class HTMLTagParser(HTMLParser):
    """Parser to extract HTML tags from text"""
    def __init__(self):
        super().__init__()
        self.tags = []
        self.current_tag = None
        
    def handle_starttag(self, tag, attrs):
        self.tags.append(('start', tag, dict(attrs)))
        
    def handle_endtag(self, tag):
        self.tags.append(('end', tag, {}))
        
    def handle_startendtag(self, tag, attrs):
        self.tags.append(('startend', tag, dict(attrs)))


def extract_html_tags(text: str) -> List[Tuple[str, str, Dict]]:
    """
    Extract HTML tags from text.
    
    Returns:
        List of (type, tag_name, attributes) tuples
    """
    parser = HTMLTagParser()
    try:
        parser.feed(text)
        return parser.tags
    except:
        # If parsing fails, try regex fallback
        tags = []
        # Match opening tags
        for match in re.finditer(r'<([a-zA-Z][a-zA-Z0-9]*)([^>]*)>', text):
            tag_name = match.group(1)
            attrs_str = match.group(2)
            attrs = {}
            # Simple attribute extraction
            for attr_match in re.finditer(r'(\w+)=["\']([^"\']*)["\']', attrs_str):
                attrs[attr_match.group(1)] = attr_match.group(2)
            tags.append(('start', tag_name, attrs))
        # Match closing tags
        for match in re.finditer(r'</([a-zA-Z][a-zA-Z0-9]*)>', text):
            tags.append(('end', match.group(1), {}))
        return tags


def check_html_xml_tags(source: str, target: str, key: Optional[str] = None) -> List[Issue]:
    """
    Check HTML/XML tag consistency.
    
    Args:
        source: Source string
        target: Target translation string
        key: Optional key for context
        
    Returns:
        List of HTML/XML tag issues
    """
    issues = []
    
    source_tags = extract_html_tags(source)
    target_tags = extract_html_tags(target)
    
    # Build tag stack for source
    source_stack = []
    source_tag_map = {}
    for tag_type, tag_name, attrs in source_tags:
        if tag_type == 'start':
            source_stack.append(tag_name)
            if tag_name not in source_tag_map:
                source_tag_map[tag_name] = []
            source_tag_map[tag_name].append(attrs)
        elif tag_type == 'end':
            if source_stack and source_stack[-1] == tag_name:
                source_stack.pop()
            else:
                # Mismatched closing tag
                issues.append(Issue('error', 'html_xml',
                    f'Source has mismatched closing tag: </{tag_name}>', key))
        elif tag_type == 'startend':
            # Self-closing tag
            if tag_name not in source_tag_map:
                source_tag_map[tag_name] = []
            source_tag_map[tag_name].append(attrs)
    
    # Build tag stack for target
    target_stack = []
    target_tag_map = {}
    for tag_type, tag_name, attrs in target_tags:
        if tag_type == 'start':
            target_stack.append(tag_name)
            if tag_name not in target_tag_map:
                target_tag_map[tag_name] = []
            target_tag_map[tag_name].append(attrs)
        elif tag_type == 'end':
            if target_stack and target_stack[-1] == tag_name:
                target_stack.pop()
            else:
                # Mismatched closing tag
                issues.append(Issue('error', 'html_xml',
                    f'Translation has mismatched closing tag: </{tag_name}>', key))
        elif tag_type == 'startend':
            # Self-closing tag
            if tag_name not in target_tag_map:
                target_tag_map[tag_name] = []
            target_tag_map[tag_name].append(attrs)
    
    # Check for unclosed tags
    if source_stack:
        issues.append(Issue('error', 'html_xml',
            f'Source has unclosed tags: {", ".join(source_stack)}', key))
    if target_stack:
        issues.append(Issue('error', 'html_xml',
            f'Translation has unclosed tags: {", ".join(target_stack)}', key))
    
    # Check tag counts
    for tag_name in set(list(source_tag_map.keys()) + list(target_tag_map.keys())):
        source_count = len(source_tag_map.get(tag_name, []))
        target_count = len(target_tag_map.get(tag_name, []))
        if source_count != target_count:
            issues.append(Issue('error', 'html_xml',
                f'Tag <{tag_name}> count mismatch: source has {source_count}, translation has {target_count}', key))
    
    # Check for missing tags
    for tag_name in source_tag_map:
        if tag_name not in target_tag_map:
            issues.append(Issue('error', 'html_xml',
                f'Missing tag in translation: <{tag_name}>', key))
    
    # Check for extra tags
    for tag_name in target_tag_map:
        if tag_name not in source_tag_map:
            issues.append(Issue('warning', 'html_xml',
                f'Extra tag in translation: <{tag_name}>', key))
    
    # Check tag attributes (especially for placeholders in attributes)
    for tag_name in source_tag_map:
        if tag_name in target_tag_map:
            source_attrs_list = source_tag_map[tag_name]
            target_attrs_list = target_tag_map[tag_name]
            if len(source_attrs_list) == len(target_attrs_list):
                for src_attrs, tgt_attrs in zip(source_attrs_list, target_attrs_list):
                    # Check if attributes with placeholders match
                    for attr_name in src_attrs:
                        if attr_name in tgt_attrs:
                            src_val = src_attrs[attr_name]
                            tgt_val = tgt_attrs[attr_name]
                            # Check placeholders in attribute values
                            src_pl = extract_placeholders(src_val)
                            tgt_pl = extract_placeholders(tgt_val)
                            # Simple check: count total placeholders
                            src_pl_count = sum(len(v) for v in src_pl.values())
                            tgt_pl_count = sum(len(v) for v in tgt_pl.values())
                            if src_pl_count != tgt_pl_count:
                                issues.append(Issue('error', 'html_xml',
                                    f'Placeholder count mismatch in <{tag_name}> {attr_name} attribute: source has {src_pl_count}, translation has {tgt_pl_count}', key))
    
    return issues


def check_non_translatable_tokens(source: str, target: str, key: Optional[str] = None) -> List[Issue]:
    """
    Check non-translatable tokens consistency.
    
    Args:
        source: Source string
        target: Target translation string
        key: Optional key for context
        
    Returns:
        List of token-related issues
    """
    issues = []
    
    # Extract tokens (already handled in placeholders, but check specific patterns)
    # Common non-translatable patterns
    token_patterns = [
        (r'\{[a-zA-Z_][a-zA-Z0-9_]*\}', 'brace_variable'),  # {variable}
        (r'\{[0-9]+\}', 'brace_number'),  # {0}, {1}
        (r'%\{[^}]+\}', 'percent_brace'),  # %{count}
        (r'\$[a-zA-Z_][a-zA-Z0-9_]*', 'dollar_variable'),  # $variable
        (r'\$\{[^}]+\}', 'dollar_brace'),  # ${variable}
        (r'@[a-zA-Z_][a-zA-Z0-9_]*', 'at_variable'),  # @name
        (r'\{\{[^}]+\}\}', 'mustache'),  # {{mustache}}
    ]
    
    source_tokens = {}
    target_tokens = {}
    
    for pattern, token_type in token_patterns:
        source_matches = re.findall(pattern, source)
        target_matches = re.findall(pattern, target)
        
        source_tokens[token_type] = source_matches
        target_tokens[token_type] = target_matches
    
    # Check each token type
    for token_type in source_tokens:
        source_toks = source_tokens[token_type]
        target_toks = target_tokens[token_type]
        
        # Count occurrences
        source_counts = {}
        for tok in source_toks:
            source_counts[tok] = source_counts.get(tok, 0) + 1
        
        target_counts = {}
        for tok in target_toks:
            target_counts[tok] = target_counts.get(tok, 0) + 1
        
        # Check for missing tokens
        for tok, count in source_counts.items():
            if tok not in target_counts:
                issues.append(Issue('error', 'tokens',
                    f'Missing non-translatable token in translation: {tok} (appears {count} time(s) in source)', key))
            elif target_counts[tok] < count:
                issues.append(Issue('error', 'tokens',
                    f'Token {tok} appears {count} time(s) in source but only {target_counts[tok]} time(s) in translation', key))
        
        # Check for extra tokens
        for tok, count in target_counts.items():
            if tok not in source_counts:
                issues.append(Issue('warning', 'tokens',
                    f'Extra token in translation: {tok} (not in source)', key))
    
    return issues


def validate_translation(source: str, target: str, key: Optional[str] = None) -> List[Issue]:
    """
    Run all validation checks on a translation pair.
    
    Args:
        source: Source string
        target: Target translation string
        key: Optional key for context
        
    Returns:
        List of all issues found
    """
    issues = []
    
    # Only validate if target is not empty
    if not target or not target.strip():
        return issues
    
    # Run all checks
    issues.extend(check_formatting(source, target, key))
    issues.extend(check_placeholders(source, target, key))
    issues.extend(check_numbers(source, target, key))
    issues.extend(check_html_xml_tags(source, target, key))
    issues.extend(check_non_translatable_tokens(source, target, key))
    
    return issues

