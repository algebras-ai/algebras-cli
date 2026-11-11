"""
Layout-preserving updates of TypeScript translation modules.

A translated module is written as text edits, never re-serialized:

- target exists: only literals whose value changed are replaced (each in its own quote style,
  escaped for it); a key the target lacks is inserted at its source position inside the right
  object (after the preceding source sibling the object has, else before the following one, else
  at the end), a missing parent object the same way. Comments, key order, blank lines,
  indentation, line endings and keys the source no longer has stay as they are;
- target does not exist: the source module is the template. Its values are replaced, the export
  is renamed (`export const en` -> `export const fr`), and string values without a translation
  (rejected placeholders, failed batch) are left out instead of keeping the source text.

The result is parsed again and must hold exactly the intended values, otherwise LayoutError is
raised and the caller falls back to writing the module from scratch.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from algebras.utils.ts_handler import (
    _EXPORT_RE,
    KeyPath,
    TSDocument,
    TSEntry,
    TSObject,
    TSParseError,
    _choose_quote,
    _format_ts_key,
    encode_ts_string,
    parse_ts_module,
)


class LayoutError(ValueError):
    """The update cannot be made as text edits; the module has to be written from scratch."""


def _line_start(text: str, i: int) -> int:
    return text.rfind("\n", 0, i) + 1


def _line_end(text: str, i: int) -> int:
    j = text.find("\n", i)
    return len(text) if j == -1 else j + 1


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def resolve_path(key: str, *docs: Optional[TSDocument]) -> KeyPath:
    """The key path a dotted translation key names (a key with a dot in it if a module has one)."""
    split = tuple(key.split("."))
    for doc in docs:
        if doc is not None and split in doc.literals:
            return split
    for doc in docs:
        if doc is not None and (key,) in doc.literals:
            return (key,)
    return split


def _get(data: Any, path: KeyPath) -> Any:
    for part in path:
        if isinstance(data, dict) and part in data:
            data = data[part]
        elif isinstance(data, list) and part.isdigit() and int(part) < len(data):
            data = data[int(part)]
        else:
            return None
    return data


def set_path(data: Dict[str, Any], path: KeyPath, value: Any) -> None:
    node: Any = data
    for part in path[:-1]:
        if isinstance(node, dict):
            if not isinstance(node.get(part), (dict, list)):
                node[part] = {}
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            raise LayoutError(f"Cannot place {'.'.join(path)}")
    last = path[-1]
    if isinstance(node, dict):
        node[last] = value
    elif isinstance(node, list) and last.isdigit() and int(last) < len(node):
        node[int(last)] = value
    else:
        raise LayoutError(f"Cannot place {'.'.join(path)}")


def _has_strings(value: Any) -> bool:
    if isinstance(value, str):
        return True
    if isinstance(value, dict):
        return any(_has_strings(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_strings(v) for v in value)
    return False


class _Pruner:
    """Template mode: which source values stay (translated strings and non-string values)."""

    def __init__(self, translated: set):
        self.translated = translated

    def keep(self, path: KeyPath, value: Any) -> bool:
        if isinstance(value, str):
            return path in self.translated
        if isinstance(value, dict):
            if not _has_strings(value):
                return True
            return any(self.keep(path + (k,), v) for k, v in value.items())
        if isinstance(value, list):
            flags = [self.keep(path + (str(i),), v) for i, v in enumerate(value) if _has_strings(v)]
            if not flags:
                return True
            if all(flags):
                return True
            if not any(flags):
                return False
            raise LayoutError(f"Array {'.'.join(path)} is only partly translated")
        return True

    def prune(self, path: KeyPath, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self.prune(path + (k,), v) for k, v in value.items() if self.keep(path + (k,), v)}
        if isinstance(value, list):
            return [self.prune(path + (str(i),), v) for i, v in enumerate(value)]
        return value


def _indent_step(doc: TSDocument) -> str:
    text = doc.text
    for path, obj in doc.objects.items():
        if not path or not obj.entries:
            continue
        parent = doc.objects.get(path[:-1])
        entry = next((e for e in parent.entries if e.key == path[-1]), None) if parent else None
        if entry is None:
            continue
        child_ws = text[_line_start(text, obj.entries[0].key_start) : obj.entries[0].key_start]
        parent_ws = text[_line_start(text, entry.key_start) : entry.key_start]
        if child_ws.strip() or parent_ws.strip():
            continue
        if child_ws.startswith(parent_ws) and len(child_ws) > len(parent_ws):
            return child_ws[len(parent_ws) :]
    root = doc.objects.get(())
    if root and root.entries:
        ws = text[_line_start(text, root.entries[0].key_start) : root.entries[0].key_start]
        if ws and not ws.strip():
            return ws
    return "  "


def _own_line(text: str, entry: TSEntry) -> bool:
    """The entry starts its line and nothing but a // comment follows it on its last line."""
    if text[_line_start(text, entry.key_start) : entry.key_start].strip():
        return False
    after = entry.comma + 1 if entry.comma is not None else entry.value_end
    rest = text[after : _line_end(text, after)].strip()
    return rest == "" or rest.startswith("//")


def _multiline(text: str, obj: TSObject) -> bool:
    return "\n" in text[obj.start : obj.end]


class _Edits:
    def __init__(self) -> None:
        self.items: List[Tuple[int, int, int, int, str]] = []

    def insert(self, offset: int, text: str) -> None:
        self.items.append((offset, 0, len(self.items), offset, text))

    def replace(self, start: int, end: int, text: str) -> None:
        self.items.append((start, 1, len(self.items), end, text))

    def apply(self, text: str) -> str:
        # From the end: offsets stay valid. At the same offset a removal goes before an insertion,
        # and insertions keep the order they were made in.
        for start, _kind, _seq, end, new in sorted(self.items, key=lambda e: (e[0], e[1], e[2]), reverse=True):
            text = text[:start] + new + text[end:]
        return text


class _Updater:
    def __init__(
        self,
        base: TSDocument,
        source: Optional[TSDocument],
        values: Dict[KeyPath, str],
        template: bool,
    ):
        self.base = base
        self.text = base.text
        self.source = source
        self.values = values
        self.template = template
        self.nl = _newline(self.text)
        self.step = _indent_step(base)
        self.edits = _Edits()
        self.removed: Dict[KeyPath, set] = {}

    # -- rendering ---------------------------------------------------------

    def _key_text(self, path: KeyPath) -> str:
        """The key as the source writes it (quoted or not), else as an identifier if it can be."""
        if self.source is not None:
            obj = self.source.objects.get(path[:-1])
            if obj is not None:
                for entry in obj.entries:
                    if entry.key == path[-1]:
                        return self.source.text[entry.key_start : entry.key_end]
        return _format_ts_key(path[-1])

    def _value_text(self, path: KeyPath, value: Any, pad: str) -> str:
        if isinstance(value, str):
            source_literal = self.source.literals.get(path) if self.source is not None else None
            quote, subs = _choose_quote(None, source_literal)
            if quote == "`" and subs is None:
                subs = ()
            return encode_ts_string(value, quote, subs)
        if isinstance(value, dict):
            if not value:
                return "{}"
            inner = pad + self.step
            lines = ["{"]
            for key in self._order(path, list(value)):
                lines.append(f"{inner}{self._key_text(path + (key,))}: {self._value_text(path + (key,), value[key], inner)},")
            lines.append(f"{pad}}}")
            return self.nl.join(lines)
        raise LayoutError(f"Cannot insert {'.'.join(path)}")

    def _order(self, path: KeyPath, keys: List[str]) -> List[str]:
        """`keys` in source order, keys the source lacks after them."""
        source_keys: List[str] = []
        if self.source is not None and path in self.source.objects:
            source_keys = [e.key for e in self.source.objects[path].entries]
        return [k for k in source_keys if k in keys] + [k for k in keys if k not in source_keys]

    # -- edits -------------------------------------------------------------

    def replace_values(self) -> None:
        base = self.base
        for path, value in self.values.items():
            literal = base.literals.get(path)
            if literal is None:
                continue
            if _get(base.data, path) == value:
                continue
            source_literal = self.source.literals.get(path) if self.source is not None else None
            quote, subs = _choose_quote(literal, source_literal)
            self.edits.replace(literal.start, literal.end, encode_ts_string(value, quote, subs))

    def remove_untranslated(self, pruner: _Pruner, path: KeyPath = ()) -> None:
        obj = self.base.objects.get(path)
        if obj is None:
            return
        data = _get(self.base.data, path)
        removed = self.removed.setdefault(path, set())
        for entry in obj.entries:
            child = path + (entry.key,)
            value = data.get(entry.key) if isinstance(data, dict) else None
            if not pruner.keep(child, value):
                removed.add(entry.key)
                start, end = self._removal_span(entry)
                self.edits.replace(start, end, "")
            elif isinstance(value, dict):
                self.remove_untranslated(pruner, child)

    def _removal_span(self, entry: TSEntry) -> Tuple[int, int]:
        text = self.text
        after = entry.comma + 1 if entry.comma is not None else entry.value_end
        if _own_line(text, entry):
            return _line_start(text, entry.key_start), _line_end(text, after)
        end = after
        while end < len(text) and text[end] in " \t":
            end += 1
        return entry.key_start, end

    def insert_missing(self) -> None:
        # (object path, key) -> subtree of values to insert there
        pending: Dict[KeyPath, Dict[str, Any]] = {}
        for path, value in self.values.items():
            if path in self.base.literals:
                continue
            parent: KeyPath = ()
            for depth in range(len(path)):
                prefix = path[: depth + 1]
                if prefix in self.base.objects and depth + 1 < len(path):
                    parent = prefix
                    continue
                break
            key = path[len(parent)]
            if _get(self.base.data, parent + (key,)) is not None:
                # The target has something else there (a string where the source has an object,
                # or an array): not an insertion.
                raise LayoutError(f"{'.'.join(path)} does not match the target's structure")
            subtree = pending.setdefault(parent, {})
            rest = path[len(parent) + 1 :]
            if not rest:
                subtree[key] = value
            else:
                node = subtree.setdefault(key, {})
                if not isinstance(node, dict):
                    raise LayoutError(f"{'.'.join(path)} conflicts with another value")
                set_path(node, rest, value)
        for parent, children in pending.items():
            self._insert_into(parent, children)

    def _insert_into(self, path: KeyPath, children: Dict[str, Any]) -> None:
        text = self.text
        obj = self.base.objects[path]
        removed = self.removed.get(path, set())
        present = {e.key: e for e in obj.entries if e.key not in removed}
        ref = self._order(path, list(present) + [k for k in children if k not in present])

        groups: Dict[Tuple[str, str], List[str]] = {}
        for key in self._order(path, list(children)):
            i = ref.index(key)
            anchor = next((("after", k) for k in reversed(ref[:i]) if k in present), None)
            if anchor is None:
                anchor = next((("before", k) for k in ref[i + 1 :] if k in present), None)
            if anchor is None:
                anchor = ("after", obj.entries[-1].key) if obj.entries and obj.entries[-1].key in present else ("end", "")
            groups.setdefault(anchor, []).append(key)

        multi = _multiline(text, obj)
        own = [e for e in obj.entries if _own_line(text, e)]
        if own:
            pad = text[_line_start(text, own[0].key_start) : own[0].key_start]
        else:
            pad = text[_line_start(text, obj.start) : obj.start]
            pad = (pad[: len(pad) - len(pad.lstrip())] if pad.strip() else pad) + self.step

        for (where, anchor_key), keys in groups.items():
            rendered = [f"{self._key_text(path + (k,))}: {self._value_text(path + (k,), children[k], pad)}" for k in keys]
            if where == "end":
                if obj.entries:
                    raise LayoutError("Object has no entry to insert after")
                open_pad = text[_line_start(text, obj.start) : obj.start]
                open_pad = open_pad[: len(open_pad) - len(open_pad.lstrip())]
                inner = open_pad + self.step
                rendered = [f"{self._key_text(path + (k,))}: {self._value_text(path + (k,), children[k], inner)}" for k in keys]
                body = "".join(f"{inner}{r},{self.nl}" for r in rendered)
                self.edits.replace(obj.start, obj.end, "{" + self.nl + body + open_pad + "}")
                continue
            entry = present[anchor_key]
            if where == "after":
                last_without_comma = entry.comma is None
                if multi and _own_line(text, entry):
                    if last_without_comma:
                        self.edits.insert(entry.value_end, ",")
                    after = entry.comma + 1 if entry.comma is not None else entry.value_end
                    body = "".join(
                        f"{pad}{r}{'' if (last_without_comma and n == len(rendered) - 1) else ','}{self.nl}"
                        for n, r in enumerate(rendered)
                    )
                    self.edits.insert(_line_end(text, after), body)
                elif entry.comma is not None:
                    self.edits.insert(entry.comma + 1, "".join(f" {r}," for r in rendered))
                else:
                    self.edits.insert(entry.value_end, "".join(f", {r}" for r in rendered))
            else:  # before
                if multi and _own_line(text, entry):
                    offset = _line_start(text, entry.key_start)
                    floor = _line_end(text, obj.start)
                    while offset > floor:
                        previous = _line_start(text, offset - 1)
                        if not text[previous:offset].strip().startswith("//"):
                            break
                        offset = previous
                    self.edits.insert(offset, "".join(f"{pad}{r},{self.nl}" for r in rendered))
                else:
                    self.edits.insert(entry.key_start, "".join(f"{r}, " for r in rendered))

    def rename_export(self, export_name: Optional[str]) -> None:
        if not export_name:
            return
        match = _EXPORT_RE.search(self.text)
        if not match or not match.group(1) or match.group(1) == export_name:
            return
        old = match.group(1)
        self.edits.replace(match.start(1), match.end(1), export_name)
        root = self.base.objects.get(())
        if root is None:
            return
        # References to the constant after the object: `typeof en`, `export default en`.
        pattern = re.compile(r"\b(typeof|export\s+default)(\s+)" + re.escape(old) + r"\b")
        for m in pattern.finditer(self.text, root.end):
            self.edits.replace(m.start(), m.end(), f"{m.group(1)}{m.group(2)}{export_name}")


def render_ts_update(
    base_text: Optional[str],
    source_text: Optional[str],
    translations: Dict[str, Any],
    export_name: Optional[str] = None,
) -> str:
    """
    The module text with `translations` (dotted keys -> strings) written into it.

    With base_text (the existing target) it is updated in place; without, the source module is
    the template. Raises LayoutError if that cannot be done as text edits.
    """
    try:
        source = parse_ts_module(source_text) if source_text is not None else None
    except TSParseError:
        source = None
    template = base_text is None
    if template:
        if source is None:
            raise LayoutError("No source module to use as a template")
        base = source
    else:
        try:
            base = parse_ts_module(base_text)
        except TSParseError as e:
            raise LayoutError(str(e)) from e

    values: Dict[KeyPath, str] = {}
    for key, value in translations.items():
        if not isinstance(value, str):
            raise LayoutError(f"{key} is not a string")
        values[resolve_path(key, base, source)] = value

    updater = _Updater(base, source, values, template)
    if template:
        pruner = _Pruner(set(values))
        expected = pruner.prune((), base.data)
        updater.remove_untranslated(pruner)
        updater.rename_export(export_name)
    else:
        import copy

        expected = copy.deepcopy(base.data)
    for path, value in values.items():
        set_path(expected, path, value)
    updater.replace_values()
    updater.insert_missing()

    new_text = updater.edits.apply(base.text)
    try:
        written = parse_ts_module(new_text)
    except TSParseError as e:
        raise LayoutError(f"Update would not parse: {e}") from e
    if written.data != expected:
        raise LayoutError("Update would not hold the intended values")
    return new_text
