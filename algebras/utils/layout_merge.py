"""
Layout-preserving writes for line-oriented key/value files (iOS .strings, Android strings.xml).

A file is seen as a list of items (entries, comments, other elements) with their spans in the
text. Writers work on the text itself, so every byte they do not need to change stays as it was:
comments, order, blank lines, escaping of untouched values, line endings, the trailing newline.

- merge(): the target exists. Values are replaced through `edits`; keys new to the target are
  inserted at their source position (after the preceding source key the target has, otherwise
  before the following one, otherwise at the end), copied from the source with the comments
  attached to them.
- build_from_template(): the target does not exist. The source text is the template: kept
  entries get the translated text, every other entry is left out with its attached comments.

The format modules tokenize the text and render entries; this module only places text.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

ENTRY = "entry"
COMMENT = "comment"
OTHER = "other"

Edit = Tuple[int, int, str]


@dataclass
class Item:
    kind: str  # ENTRY, COMMENT or OTHER
    start: int
    end: int
    key: Optional[str] = None


def newline_of(text: str, default: str = "\n") -> str:
    """The file's line ending: CRLF if it uses one, else LF (or `default` for a one-line text)."""
    if "\r\n" in text:
        return "\r\n"
    if "\n" in text:
        return "\n"
    return default


def to_newline(text: str, nl: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", nl)


def _line_start(text: str, pos: int) -> int:
    return text.rfind("\n", 0, pos) + 1


def _line_end(text: str, pos: int) -> int:
    """Position of the line break after `pos` (before the \\r of a CRLF), or the end of text."""
    n = text.find("\n", pos)
    if n < 0:
        n = len(text)
    if n > pos and text[n - 1] == "\r":
        n -= 1
    return n


def block_span(text: str, items: Sequence[Item], i: int) -> Tuple[int, int]:
    """
    Span of item i with the comments attached to it: comment lines right above it (no blank line
    between) and a comment on the same line after it. Whole lines when the item has its lines to
    itself. The end excludes the line break.
    """
    start = items[i].start
    j = i - 1
    while j >= 0 and items[j].kind == COMMENT:
        gap = text[items[j].end:start]
        if gap.strip() or gap.count("\n") > 1:
            break
        # A comment on the same line as the item before it belongs to that item.
        if j > 0 and "\n" not in text[items[j - 1].end:items[j].start]:
            break
        start = items[j].start
        j -= 1
    ls = _line_start(text, start)
    if not text[ls:start].strip():
        start = ls

    end = items[i].end
    k = i + 1
    if k < len(items) and items[k].kind == COMMENT:
        gap = text[end:items[k].start]
        if not gap.strip() and "\n" not in gap:
            end = items[k].end
    le = _line_end(text, end)
    if not text[end:le].strip():
        end = le
    return start, end


def _newlines_before(text: str, items: Sequence[Item], i: int, span_start: int) -> int:
    """Line breaks between the item before block i and the block (1 if none, i.e. at the top)."""
    if i == 0:
        return 1
    prev_end = block_span(text, items, i - 1)[1]
    gap = text[prev_end:span_start]
    return max(1, gap.count("\n")) if not gap.strip() else 1


def _newlines_after(text: str, span_end: int) -> int:
    rest = text[span_end:]
    ws = rest[: len(rest) - len(rest.lstrip())]
    return max(1, ws.count("\n"))


def apply_edits(text: str, edits: List[Edit]) -> str:
    """Apply non-overlapping (start, end, replacement) edits; insertions have start == end."""
    out = []
    pos = 0
    for start, end, replacement in sorted(edits, key=lambda e: (e[0], e[1])):
        if start < pos:
            raise ValueError("overlapping edits")
        out.append(text[pos:start])
        out.append(replacement)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def merge(
    target_text: str,
    target_items: Sequence[Item],
    source_text: str,
    source_items: Sequence[Item],
    new_source_indices: Sequence[int],
    render_item: Callable[[int], str],
    edits: List[Edit],
    orphan_texts: Sequence[str] = (),
    empty_insert: Optional[Tuple[int, str, str]] = None,
) -> str:
    """
    Apply `edits` to the target and insert the source entries `new_source_indices` (indices into
    source_items) at their source position.

    render_item(i) is the text of source item i as it goes into the target (translated value);
    the comments attached to it are copied along. orphan_texts (entries with no source position)
    go at the end. empty_insert = (pos, prefix, suffix) says where the end is when the target has
    no items at all.
    """
    nl = newline_of(target_text, newline_of(source_text))
    target_index: Dict[str, int] = {}
    for i, item in enumerate(target_items):
        if item.kind == ENTRY and item.key is not None:
            target_index.setdefault(item.key, i)
    to_insert = set(new_source_indices)

    def block(i: int) -> str:
        bs, be = block_span(source_text, source_items, i)
        item = source_items[i]
        text = source_text[bs:item.start] + render_item(i) + source_text[item.end:be]
        return to_newline(text, nl)

    def sep(i: int) -> str:
        bs, _ = block_span(source_text, source_items, i)
        return nl * _newlines_before(source_text, source_items, i, bs)

    # Group the new entries by where they go, in source order.
    after: Dict[str, List[int]] = {}
    before: List[int] = []
    before_key: Optional[str] = None
    anchor: Optional[str] = None
    for i, item in enumerate(source_items):
        if item.kind != ENTRY:
            continue
        if item.key in target_index:
            anchor = item.key
            if before and before_key is None:
                before_key = item.key
            continue
        if i not in to_insert:
            continue
        if anchor is None:
            before.append(i)
        else:
            after.setdefault(anchor, []).append(i)

    insertions: List[Edit] = []
    for key, indices in after.items():
        pos = block_span(target_text, target_items, target_index[key])[1]
        insertions.append((pos, pos, "".join(sep(i) + block(i) for i in indices)))

    at_end: List[str] = []
    if before:
        if before_key is not None:
            pos = block_span(target_text, target_items, target_index[before_key])[0]
            parts = []
            for n, i in enumerate(before):
                if n:
                    parts.append(sep(i))
                parts.append(block(i))
            _, last_end = block_span(source_text, source_items, before[-1])
            parts.append(nl * _newlines_after(source_text, last_end))
            insertions.append((pos, pos, "".join(parts)))
        else:
            at_end.extend(sep(i) + block(i) for i in before)
    at_end.extend(nl + to_newline(t, nl) for t in orphan_texts)

    if at_end:
        if target_items:
            pos = block_span(target_text, target_items, len(target_items) - 1)[1]
            insertions.append((pos, pos, "".join(at_end)))
        else:
            pos, prefix, suffix = empty_insert if empty_insert is not None else (0, "", nl)
            # The first block needs no line break before it.
            body = "".join(at_end).lstrip("\r\n")
            insertions.append((pos, pos, prefix + body + suffix))

    return apply_edits(target_text, list(edits) + insertions)


def deletion_span(text: str, items: Sequence[Item], i: int) -> Tuple[int, int]:
    """
    What to cut to leave item i (with its attached comments) out: the block and the line break
    and blank lines before it, so the spacing around it reads as if it was never there.
    """
    start, end = block_span(text, items, i)
    q = len(text[:start].rstrip())
    if q == 0:
        rest = text[end:]
        nxt = end + len(rest) - len(rest.lstrip())
        return start, (_line_start(text, nxt) if nxt < len(text) else len(text))
    le = _line_end(text, q)
    return (le if le <= start else q), end


def build_from_template(
    source_text: str,
    source_items: Sequence[Item],
    keep: Callable[[int], bool],
    render_item: Callable[[int], str],
    extra_edits: Sequence[Edit] = (),
) -> str:
    """
    The source text with each kept entry rendered and every other entry / OTHER item left out.
    Comments not attached to a left-out item stay.
    """
    edits: List[Edit] = list(extra_edits)
    dropped = set()
    for i, item in enumerate(source_items):
        if item.kind == COMMENT:
            continue
        if item.kind == ENTRY and keep(i):
            edits.append((item.start, item.end, render_item(i)))
        else:
            dropped.add(i)
    for i in sorted(dropped):
        start, end = deletion_span(source_text, source_items, i)
        edits.append((start, end, ""))
    return apply_edits(source_text, edits)
