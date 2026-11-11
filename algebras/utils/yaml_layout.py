"""
Layout-preserving writes of translated YAML locale files.

`yaml.dump` sorts keys, drops comments and changes quoting, so translated files are written as
text edits located with PyYAML's node marks (yaml.compose), as `algebras placeholders --fix` does
(yaml_format.write_fixes):

- target exists: only values that changed are replaced; a key the target lacks is inserted at its
  source position inside the right mapping (after the preceding source sibling the mapping has,
  else before the following one, else at its end), a missing parent mapping the same way. Comments,
  key order, blank lines, the quoting of untouched values, indentation, line endings and the final
  newline stay; keys the source no longer has stay too;
- target does not exist: the source file is the template, with its values replaced. A Rails root
  (`en:`) becomes the target locale (`ru:`), values without a translation (rejected placeholders,
  failed batch) are left out, and plural forms the target language needs but the source lacks
  (ru few/many) are inserted in CLDR order.

Scalars keep their style where the value allows it and are quoted only when needed (a value that
starts with `%`, `{` or `@`, or would load as another type, is quoted). The result is parsed again
and must load as exactly the intended content, otherwise YAMLLayoutError is raised and the caller
falls back to yaml.dump.
"""

import copy
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import yaml

from algebras.utils.yaml_locale_root import locale_root

_MERGE_TAG = "tag:yaml.org,2002:merge"


class YAMLLayoutError(ValueError):
    """The update cannot be made as text edits; the file has to be dumped from scratch."""


def _line_start(text: str, i: int) -> int:
    return text.rfind("\n", 0, i) + 1


def _line_end(text: str, i: int) -> int:
    j = text.find("\n", i)
    return len(text) if j == -1 else j + 1


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _str_keys(obj: Any) -> Any:
    """Content with every mapping key as a string (`no:` is "False"), as the CLI names keys."""
    if isinstance(obj, dict):
        return {str(k): _str_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_str_keys(v) for v in obj]
    return obj


def _same(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


def _merge(base: Any, content: Any) -> Any:
    """Existing target: content's values over the target's, every other target key kept."""
    if isinstance(base, dict) and isinstance(content, dict):
        merged = dict(base)
        for key, value in content.items():
            merged[key] = _merge(base[key], value) if key in base else copy.deepcopy(value)
        return merged
    return copy.deepcopy(content)


def _prune_merge(base: Any, content: Any) -> Any:
    """Template: the source's structure with only the keys content has, holding content's values."""
    if isinstance(base, dict) and isinstance(content, dict):
        return {
            key: (_prune_merge(base[key], value) if key in base else copy.deepcopy(value))
            for key, value in content.items()
        }
    return copy.deepcopy(content)


def _at(data: Any, path: Tuple[str, ...]) -> Any:
    for part in path:
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


def _check_editable(node: Any, seen: set) -> None:
    """Aliases and merge keys share nodes between paths: a text edit could change several keys."""
    if id(node) in seen:
        raise YAMLLayoutError("File uses aliases")
    seen.add(id(node))
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            if key_node.tag == _MERGE_TAG:
                raise YAMLLayoutError("File uses merge keys")
            _check_editable(key_node, seen)
            _check_editable(value_node, seen)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _check_editable(item, seen)


def _content_end(text: str, node: Any) -> int:
    """Offset after the last character of a node's own text (trailing breaks, comments excluded)."""
    if isinstance(node, yaml.ScalarNode):
        end = node.end_mark.index
        if node.style in ("|", ">"):
            span = text[node.start_mark.index : end]
            end = node.start_mark.index + len(span.rstrip("\r\n"))
        return end
    if not node.flow_style and node.value:
        last = node.value[-1]
        return _content_end(text, last[1] if isinstance(node, yaml.MappingNode) else last)
    return node.end_mark.index


def _plain_ok(value: str) -> bool:
    """`value` can be a plain scalar in a block mapping: it loads back as this same string."""
    if not value or value != value.strip() or "\n" in value or "\r" in value:
        return False
    if value.startswith(("%", "{", "@", "`")) or not all(ch.isprintable() for ch in value):
        return False
    try:
        return yaml.safe_load(f"k: {value}") == {"k": value}
    except yaml.YAMLError:
        return False


def render_value(value: Any, style: Optional[str] = None) -> str:
    """A one-line YAML scalar that loads back as `value`, in `style` where possible."""
    from algebras.services.placeholders.formats.yaml_format import render_scalar

    if isinstance(value, str):
        if style in (None, ""):
            return value if _plain_ok(value) else render_scalar(value, "'")
        return render_scalar(value, style)
    if value is None or isinstance(value, (bool, int, float)):
        return json.dumps(value)
    return _flow(value)


def _flow(value: Any) -> str:
    """Flow (JSON-like) YAML for a mapping or list; every string double-quoted."""
    from algebras.services.placeholders.formats.yaml_format import _double_quoted

    if isinstance(value, dict):
        return "{" + ", ".join(f"{_double_quoted(str(k))}: {_flow(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_flow(v) for v in value) + "]"
    if isinstance(value, str):
        return _double_quoted(value)
    return json.dumps(value)


def render_key(key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][\w\-]*", key):
        try:
            if yaml.safe_load(f"{key}: x") == {key: "x"}:
                return key
        except yaml.YAMLError:
            pass
    return render_value(key, "'")


def _render_block(value: str, indent: str, nl: str) -> Optional[str]:
    """`value` as a literal block scalar (`|` / `|-`), or None if it cannot be one safely."""
    if not value or "\r" in value or value.endswith("\n\n"):
        return None
    if any(not (ch.isprintable() or ch in "\n\t") for ch in value):
        return None
    body = value[:-1] if value.endswith("\n") else value
    lines = body.split("\n")
    first = next((line for line in lines if line), None)
    if first is None or first[0] in " \t" or lines[-1] == "":
        return None
    header = "|" if value.endswith("\n") else "|-"
    return header + "".join(nl + (indent + line if line else "") for line in lines)


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


def _plural_group(value: Any) -> bool:
    from algebras.services.placeholders.formats.yaml_format import is_plural_group

    return is_plural_group(value)


def _order(keys: List[str], content: Any, source: Any) -> List[str]:
    """`keys` in the order a mapping lists them: CLDR order for a plural group, else source order."""
    from algebras.services.placeholders.formats.yaml_format import PLURAL_CATEGORIES

    if isinstance(content, dict) and _plural_group(content):
        ordered = [c for c in PLURAL_CATEGORIES if c in keys]
        return ordered + [k for k in keys if k not in ordered]
    source_keys = [k for k in source] if isinstance(source, dict) else []
    return [k for k in source_keys if k in keys] + [k for k in keys if k not in source_keys]


class _Updater:
    def __init__(self, text: str, root: Any, content: Dict, source: Any, template: bool, blocks: bool):
        self.text = text
        self.root = root
        self.content = content
        self.source = source
        self.template = template
        self.blocks = blocks
        self.nl = _newline(text)
        self.step = self._indent_step()
        self.edits = _Edits()
        self.rename: Optional[Tuple[str, str]] = None
        self.expected: Any = None

    # -- layout ------------------------------------------------------------

    def _indent_step(self) -> str:
        stack = [self.root]
        while stack:
            node = stack.pop()
            if not isinstance(node, yaml.MappingNode) or node.flow_style:
                continue
            for key_node, value_node in node.value:
                if isinstance(value_node, yaml.MappingNode) and not value_node.flow_style and value_node.value:
                    step = value_node.value[0][0].start_mark.column - key_node.start_mark.column
                    if step > 0:
                        return " " * step
                stack.append(value_node)
        return "  "

    def _entries(self, node: Any, path: Tuple[str, ...]) -> Dict[str, Tuple[Any, Any]]:
        from algebras.services.placeholders.formats.yaml_format import _key_name

        entries: Dict[str, Tuple[Any, Any]] = {}
        for key_node, value_node in node.value:
            name = _key_name(key_node)
            if not path and self.rename and name == self.rename[0]:
                name = self.rename[1]
            entries[name] = (key_node, value_node)
        return entries

    def _entry_end(self, value_node: Any) -> int:
        return _line_end(self.text, _content_end(self.text, value_node))

    # -- rendering ---------------------------------------------------------

    def _render_entry(self, key: str, value: Any, pad: str, source: Any) -> str:
        nl = self.nl
        k = render_key(key)
        if isinstance(value, dict):
            if not value:
                return f"{pad}{k}: {{}}{nl}"
            out = f"{pad}{k}:{nl}"
            for child in _order(list(value), value, source):
                out += self._render_entry(child, value[child], pad + self.step, _at(source, (child,)))
            return out
        if isinstance(value, list):
            if value and all(not isinstance(item, (dict, list)) for item in value):
                return f"{pad}{k}:{nl}" + "".join(f"{pad}{self.step}- {render_value(item)}{nl}" for item in value)
            return f"{pad}{k}: {_flow(value)}{nl}"
        if self.blocks and isinstance(value, str) and "\n" in value:
            block = _render_block(value, pad + self.step, nl)
            if block:
                return f"{pad}{k}: {block}{nl}"
        return f"{pad}{k}: {render_value(value)}{nl}"

    def _replace_scalar(self, node: Any, value: Any, pad: str) -> None:
        start = node.start_mark.index
        end = _content_end(self.text, node)
        if not isinstance(node, yaml.ScalarNode):
            self.edits.replace(start, end, _flow(value))
            return
        if node.style in ("|", ">") and isinstance(value, str):
            from algebras.services.placeholders.formats.yaml_format import _double_quoted

            rendered = None
            if self.blocks:
                span = self.text[start:end]
                lines = [line for line in re.split(r"\r?\n", span)[1:] if line.strip()]
                indent = lines[0][: len(lines[0]) - len(lines[0].lstrip(" "))] if lines else pad + self.step
                rendered = _render_block(value, indent, self.nl)
            self.edits.replace(start, end, rendered or _double_quoted(value))
            return
        self.edits.replace(start, end, render_value(value, node.style))

    # -- walk --------------------------------------------------------------

    def walk(self, node: Any, content: Any, old: Any, path: Tuple[str, ...], pad: str) -> None:
        if isinstance(content, dict):
            if not isinstance(node, yaml.MappingNode):
                self._replace_scalar(node, content, pad)
                return
            self._walk_mapping(node, content, old if isinstance(old, dict) else {}, path)
        elif isinstance(content, list):
            if _same(content, old):
                return
            if isinstance(node, yaml.SequenceNode) and len(node.value) == len(content) and not node.flow_style:
                for index, (item_node, item) in enumerate(zip(node.value, content)):
                    item_old = old[index] if isinstance(old, list) and index < len(old) else None
                    self.walk(item_node, item, item_old, path + (str(index),), pad + self.step)
            else:
                self._replace_scalar(node, content, pad)
        else:
            if _same(content, old) and isinstance(node, yaml.ScalarNode):
                return
            self._replace_scalar(node, content, pad)

    def _walk_mapping(self, node: Any, content: Dict, old: Dict, path: Tuple[str, ...]) -> None:
        entries = self._entries(node, path)
        missing = [k for k in content if k not in entries]
        removed = [k for k in entries if k not in content] if self.template else []
        if not entries or (node.flow_style and (missing or removed)):
            if not entries and not node.flow_style:
                raise YAMLLayoutError(f"Empty mapping at {'.'.join(path)}")
            self.edits.replace(node.start_mark.index, node.end_mark.index, _flow(_at(self.expected, path)))
            return

        first_key = next(iter(entries.values()))[0]
        pad = " " * first_key.start_mark.column
        for key, value in content.items():
            if key in entries:
                key_node, value_node = entries[key]
                if value_node.start_mark.index < key_node.end_mark.index:
                    raise YAMLLayoutError("Value before its key (alias)")
                self.walk(value_node, value, old.get(key), path + (key,), pad)

        for key in removed:
            key_node, value_node = entries[key]
            start = _line_start(self.text, key_node.start_mark.index)
            if self.text[start : key_node.start_mark.index].strip():
                raise YAMLLayoutError(f"Cannot remove {'.'.join(path + (key,))}")
            self.edits.replace(start, self._entry_end(value_node), "")

        if missing:
            self._insert(node, entries, content, path, pad, set(removed))

    def _insert(self, node: Any, entries: Dict, content: Dict, path: Tuple[str, ...], pad: str, removed: set) -> None:
        text = self.text
        source = _at(self.source, path)
        present = [k for k in entries if k not in removed]
        missing = [k for k in content if k not in entries]
        union = present + missing
        reference = _order(union, {k: content.get(k, "") for k in union}, source)

        groups: Dict[Tuple[str, str], List[str]] = {}
        for key in _order(missing, content, source):
            i = reference.index(key)
            anchor = next((("after", k) for k in reversed(reference[:i]) if k in present), None)
            if anchor is None:
                anchor = next((("before", k) for k in reference[i + 1 :] if k in present), None)
            if anchor is None:
                anchor = ("end", "")
            groups.setdefault(anchor, []).append(key)

        for (where, anchor_key), keys in groups.items():
            body = "".join(
                self._render_entry(k, content[k], pad, _at(source, (k,))) for k in keys
            )
            if where == "before":
                key_node = entries[anchor_key][0]
                offset = _line_start(text, key_node.start_mark.index)
                if text[offset : key_node.start_mark.index].strip():
                    raise YAMLLayoutError(f"Cannot insert into {'.'.join(path)}")
                floor = _line_end(text, node.start_mark.index) if path else 0
                while offset > floor:
                    previous = _line_start(text, offset - 1)
                    if not text[previous:offset].strip().startswith("#"):
                        break
                    offset = previous
            else:
                last = entries[anchor_key][1] if where == "after" else node.value[-1][1]
                offset = self._entry_end(last)
            if offset == len(text) and text and not text.endswith("\n"):
                body = self.nl + body[: -len(self.nl)]  # the file has no final newline: keep it so
            self.edits.insert(offset, body)

    # -- run ---------------------------------------------------------------

    def run(self, old: Dict) -> str:
        root = self.root
        old_root = locale_root(old)
        new_root = locale_root(self.content)
        if old_root and new_root and old_root != new_root and len(self.content) == 1:
            self.rename = (old_root, new_root)
            key_node = root.value[0][0]
            self.edits.replace(key_node.start_mark.index, key_node.end_mark.index, render_key(new_root))
            old = {new_root: old[old_root]}
        source_root = locale_root(self.source)
        if source_root and new_root and source_root != new_root and len(self.content) == 1:
            self.source = {new_root: self.source[source_root]}
        self.expected = _prune_merge(old, self.content) if self.template else _merge(old, self.content)
        self._walk_mapping(root, self.content, old, ())
        new_text = self.edits.apply(self.text)
        try:
            written = _str_keys(yaml.safe_load(new_text))
        except yaml.YAMLError as e:
            raise YAMLLayoutError(f"Update would not parse: {e}") from e
        if written != self.expected:
            raise YAMLLayoutError("Update would not hold the intended values")
        return new_text


def render_yaml_update(base_text: Optional[str], source_text: Optional[str], content: Any) -> str:
    """
    The file text with `content` (the target's full intended content) written into it.

    base_text is the existing target; None makes the target from source_text as a template.
    Raises YAMLLayoutError if that cannot be done as text edits.
    """
    from algebras.utils.ts_handler import convert_numeric_dicts_to_lists

    template = base_text is None
    text = source_text if template else base_text
    if text is None:
        raise YAMLLayoutError("No source file to use as a template")
    content = _str_keys(convert_numeric_dicts_to_lists(content))
    if not isinstance(content, dict) or not content:
        raise YAMLLayoutError("Nothing to write")
    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
        old = _str_keys(yaml.safe_load(text))
        source = _str_keys(yaml.safe_load(source_text)) if source_text is not None else None
    except yaml.YAMLError as e:
        raise YAMLLayoutError(str(e)) from e
    if root is None and not template:
        # Empty target: every key is new.
        nl = _newline(text) if text else "\n"
        updater = _Updater("", yaml.compose("{}"), content, source, False, True)
        updater.nl = nl
        new_text = text + "".join(
            updater._render_entry(k, content[k], "", _at(source, (k,))) for k in _order(list(content), content, source)
        )
        if _str_keys(yaml.safe_load(new_text)) != content:
            raise YAMLLayoutError("Update would not hold the intended values")
        return new_text
    if not isinstance(root, yaml.MappingNode) or root.flow_style:
        raise YAMLLayoutError("Top level is not a block mapping")
    _check_editable(root, set())

    last_error: Optional[YAMLLayoutError] = None
    for blocks in (True, False):
        try:
            return _Updater(text, root, content, source, template, blocks).run(old)
        except YAMLLayoutError as e:
            last_error = e
    raise last_error  # type: ignore[misc]
