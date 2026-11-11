"""
A Python stand-in for aapt2's checks on <string> and plural <item> values, so tests can tell
whether a written strings.xml would build:

- an unescaped ' outside a double-quoted section is an error ("Apostrophe not preceded by \\");
- an unescaped " opens or closes a quoted section, so an odd number of them is an error;
- a value that starts with an unescaped @ or ? must be a valid resource reference.

The quote state carries over child elements (<b>, <xliff:g>), as in aapt2.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Union

_REFERENCE = re.compile(r"^[@?](?:[A-Za-z_][\w.]*:)?[A-Za-z_]\w*/[\w.]+$")


def _text_runs(elem: ET.Element) -> List[str]:
    runs = [elem.text or ""]
    for child in elem:
        if isinstance(child.tag, str):
            runs.extend(_text_runs(child))
        runs.append(child.tail or "")
    return runs


def value_problems(elem: ET.Element) -> List[str]:
    """aapt2 errors for one <string> / <item> element."""
    problems = []
    in_quotes = False
    for run in _text_runs(elem):
        i = 0
        while i < len(run):
            c = run[i]
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_quotes = not in_quotes
            elif c == "'" and not in_quotes:
                problems.append("Apostrophe not preceded by \\")
            i += 1
    if in_quotes:
        problems.append("Unbalanced unescaped double quote")
    has_children = any(isinstance(child.tag, str) for child in elem)
    text = (elem.text or "").strip()
    if not has_children and text[:1] in ("@", "?") and not _REFERENCE.match(text):
        problems.append(f"Invalid resource reference {text!r} (escape a literal leading @ or ?)")
    return problems


def file_problems(path: Union[str, Path]) -> List[str]:
    root = ET.parse(str(path)).getroot()
    problems = []
    for elem in root.findall("string"):
        problems += [f"string {elem.get('name')}: {p}" for p in value_problems(elem)]
    for plurals in root.findall("plurals"):
        for item in plurals.findall("item"):
            label = f"plurals {plurals.get('name')}[{item.get('quantity')}]"
            problems += [f"{label}: {p}" for p in value_problems(item)]
    return problems


def assert_aapt_valid(path: Union[str, Path]) -> None:
    problems = file_problems(path)
    assert not problems, f"{path} would not build:\n" + "\n".join(problems)
