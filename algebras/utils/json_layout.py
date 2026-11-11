"""
Layout-preserving JSON writes (JSON and Flutter ARB localization files).

`merge_json_text(base_text, desired, order=…, drop_missing=…)` returns `base_text` with its values
changed to those in `desired`, keeping everything else as it is: key order, indentation (spaces or
tabs), the space after ':', blank lines, line endings, the trailing newline, a BOM, and the escaping
of untouched strings. New strings follow the file's style for non-ASCII text (\\uXXXX escapes if the
file uses them and has no raw non-ASCII, raw UTF-8 otherwise).

- A key in `desired` but not in the base is inserted at its position in `order` (the source data):
  after the nearest preceding source key, else before the nearest following one, else at the end.
- A key in the base but not in `desired` stays (drop_missing=False, updating an existing target) or
  is removed (drop_missing=True, building a new target from the source file as a template).
"""

import json
import os
import re
from dataclasses import dataclass, field
from json.decoder import scanstring
from typing import Any, Dict, List, Optional, Tuple

_WS = re.compile(r"[ \t\n\r]*")
_ESCAPED_NON_ASCII = re.compile(r"\\u(?!00[0-7][0-9a-fA-F])[0-9a-fA-F]{4}")


@dataclass
class _Member:
    key: str
    key_start: int
    value_start: int
    value_end: int
    node: "_Node"


@dataclass
class _Node:
    kind: str  # "object", "array" or "scalar"
    start: int
    end: int
    members: List[_Member] = field(default_factory=list)  # object members
    items: List["_Node"] = field(default_factory=list)  # array items


def _parse(text: str, start: int) -> _Node:
    decoder = json.JSONDecoder()

    def ws(i: int) -> int:
        return _WS.match(text, i).end()

    def value(i: int) -> _Node:
        i = ws(i)
        ch = text[i : i + 1]
        if ch == "{":
            node = _Node("object", i, i)
            i = ws(i + 1)
            if text[i : i + 1] == "}":
                node.end = i + 1
                return node
            while True:
                i = ws(i)
                if text[i : i + 1] != '"':
                    raise ValueError(f"Expected a key at offset {i}")
                key_start = i
                key, i = scanstring(text, i + 1)
                i = ws(i)
                if text[i : i + 1] != ":":
                    raise ValueError(f"Expected ':' at offset {i}")
                child = value(i + 1)
                node.members.append(_Member(key, key_start, child.start, child.end, child))
                i = ws(child.end)
                if text[i : i + 1] == ",":
                    i += 1
                elif text[i : i + 1] == "}":
                    node.end = i + 1
                    return node
                else:
                    raise ValueError(f"Expected ',' or '}}' at offset {i}")
        if ch == "[":
            node = _Node("array", i, i)
            i = ws(i + 1)
            if text[i : i + 1] == "]":
                node.end = i + 1
                return node
            while True:
                child = value(i)
                node.items.append(child)
                i = ws(child.end)
                if text[i : i + 1] == ",":
                    i += 1
                elif text[i : i + 1] == "]":
                    node.end = i + 1
                    return node
                else:
                    raise ValueError(f"Expected ',' or ']' at offset {i}")
        _, end = decoder.raw_decode(text, i)
        return _Node("scalar", i, end)

    return value(start)


class _Style:
    """How the file is written: line endings, indent unit, the text after ':', escaping."""

    def __init__(self, text: str, root: _Node):
        self.text = text
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.ensure_ascii = bool(_ESCAPED_NON_ASCII.search(text)) and not re.search(
            r"[^\x00-\x7f]", text.lstrip("﻿")
        )
        self.unit = "  "
        self.colon = ": "
        first = root.members[0] if root.kind == "object" and root.members else None
        if first is not None:
            between = text[first.key_start : first.value_start]
            colon = between[between.rindex(":") :]
            if "\n" not in colon and "\r" not in colon:
                self.colon = colon
            indent = self.line_indent(first.key_start)
            root_indent = self.line_indent(root.start) or ""
            if indent and len(indent) > len(root_indent):
                self.unit = indent[len(root_indent) :]

    def line_indent(self, pos: int) -> Optional[str]:
        """Whitespace from the start of the line to `pos`, or None if other text precedes `pos`."""
        line_start = max(self.text.rfind("\n", 0, pos), self.text.rfind("\r", 0, pos)) + 1
        prefix = self.text[line_start:pos].lstrip("﻿")
        return prefix if not prefix.strip() else None

    def dumps(self, value: Any, indent: Optional[str]) -> str:
        """`value` as JSON in the file's style, continuation lines indented by `indent`."""
        from algebras.utils.ts_handler import convert_numeric_dicts_to_lists

        value = convert_numeric_dicts_to_lists(value)
        if indent is None:  # inside a one-line object or array
            return json.dumps(value, ensure_ascii=self.ensure_ascii, separators=(", ", self.colon))
        rendered = json.dumps(
            value, ensure_ascii=self.ensure_ascii, indent=self.unit, separators=(",", self.colon)
        )
        return rendered.replace("\n", self.newline + indent)


def _same(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


def _render(
    style: _Style,
    node: _Node,
    desired: Any,
    order: Any,
    drop_missing: bool,
    indent: Optional[str],
) -> str:
    """
    The text of `node` with the value `desired`. `indent` is the indentation of the line holding
    the node's key (None inside a one-line object or array).
    """
    text = style.text
    original = text[node.start : node.end]
    if node.kind == "object" and isinstance(desired, dict):
        return _render_object(style, node, desired, order, drop_missing, indent)
    if (
        node.kind == "array"
        and isinstance(desired, dict)
        and desired
        and all(isinstance(k, str) and k.isdigit() for k in desired)
    ):
        from algebras.utils.ts_handler import convert_numeric_dicts_to_lists

        desired = convert_numeric_dicts_to_lists(desired)
    if node.kind == "array" and isinstance(desired, list) and len(desired) == len(node.items):
        item_indent = style.line_indent(node.items[0].start) if node.items else None
        out, pos = [], node.start
        for i, item in enumerate(node.items):
            sub_order = order[i] if isinstance(order, list) and i < len(order) else None
            out.append(text[pos : item.start])
            out.append(_render(style, item, desired[i], sub_order, drop_missing, item_indent))
            pos = item.end
        out.append(text[pos : node.end])
        return "".join(out)
    if _same(json.loads(original), desired):
        return original
    return style.dumps(desired, indent)


def _render_object(
    style: _Style,
    node: _Node,
    desired: Dict[str, Any],
    order: Any,
    drop_missing: bool,
    indent: Optional[str],
) -> str:
    text = style.text
    members = node.members
    base_keys = {m.key for m in members}

    if members:
        member_indent = style.line_indent(members[0].key_start)
    else:
        member_indent = None if indent is None else indent + style.unit

    # (original member index or None, key, text)
    out: List[Tuple[Optional[int], str, str]] = []
    for index, m in enumerate(members):
        if m.key in desired:
            sub_order = order.get(m.key) if isinstance(order, dict) else None
            rendered = _render(style, m.node, desired[m.key], sub_order, drop_missing, member_indent)
            out.append((index, m.key, text[m.key_start : m.value_start] + rendered))
        elif not drop_missing:
            out.append((index, m.key, text[m.key_start : m.value_end]))

    new_keys = [k for k in desired if k not in base_keys]
    if new_keys:
        reference = list(order) if isinstance(order, dict) else []
        ref_pos = {k: i for i, k in enumerate(reference)}
        for key in sorted(new_keys, key=lambda k: (k not in ref_pos, ref_pos.get(k, 0))):
            body = (
                json.dumps(key, ensure_ascii=style.ensure_ascii)
                + style.colon
                + style.dumps(desired[key], member_indent)
            )
            placed = [k for _, k, _ in out]
            at = len(out)
            if key in ref_pos:
                prev = next((k for k in reversed(reference[: ref_pos[key]]) if k in placed), None)
                nxt = next((k for k in reference[ref_pos[key] + 1 :] if k in placed), None)
                if prev is not None:
                    at = max(i for i, k in enumerate(placed) if k == prev) + 1
                elif nxt is not None:
                    at = min(i for i, k in enumerate(placed) if k == nxt)
            out.insert(at, (None, key, body))

    if [(i, t) for i, _, t in out] == [(i, text[m.key_start : m.value_end]) for i, m in enumerate(members)]:
        return text[node.start : node.end]
    if not out:
        return "{}"

    gaps = [text[members[i].value_end : members[i + 1].key_start] for i in range(len(members) - 1)]
    if member_indent is not None:
        default_gap = "," + style.newline + member_indent
    else:
        default_gap = gaps[0] if gaps else ", "

    if members:
        leading = text[node.start + 1 : members[0].key_start]
        trailing = text[members[-1].value_end : node.end - 1]
    elif member_indent is not None:
        leading = style.newline + member_indent
        trailing = style.newline + (indent or "")
    else:
        leading = trailing = ""

    parts = ["{", leading]
    for n, (index, _, body) in enumerate(out):
        if n:
            prev_index = out[n - 1][0]
            if index is not None and index > 0 and (prev_index is None or prev_index < index):
                # The gap the member had before it (a blank line before a group stays with it).
                parts.append(gaps[index - 1])
            else:
                parts.append(default_gap)
        parts.append(body)
    parts.append(trailing)
    parts.append("}")
    return "".join(parts)


def merge_json_text(
    base_text: str,
    desired: Dict[str, Any],
    order: Optional[Dict[str, Any]] = None,
    drop_missing: bool = False,
) -> str:
    """`base_text` with the values of `desired` (see the module docstring)."""
    start = 1 if base_text.startswith("﻿") else 0
    root = _parse(base_text, start)
    if root.kind != "object":
        raise ValueError("JSON file must contain an object")
    style = _Style(base_text, root)
    indent = style.line_indent(root.start) or ""
    rendered = _render(
        style, root, desired, order if order is not None else desired, drop_missing, indent
    )
    return base_text[: root.start] + rendered + base_text[root.end :]


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_text(path: str, text: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def merge_json_file(
    target_path: str,
    desired: Dict[str, Any],
    order: Optional[Dict[str, Any]] = None,
    template_path: Optional[str] = None,
) -> None:
    """
    Update `target_path` in place (keys it has that `desired` lacks stay), or, with
    `template_path`, write it in that file's layout (keys `desired` lacks are left out).
    """
    if template_path is not None:
        text = merge_json_text(read_text(template_path), desired, order, drop_missing=True)
    else:
        original = read_text(target_path)
        text = merge_json_text(original, desired, order, drop_missing=False)
        if text == original:
            return
    write_text(target_path, text)
