"""
Java .properties: java.text.MessageFormat, String.format and ${…} placeholders.

- MessageFormat arguments {0}, {1,number}, {0,number,#.##}, {2,date,short} are masked whole.
- {0,choice,0#no files|1#one file|1<{0,number,integer} files}: only the syntax is masked (the
  head with the first limit, every "|limit#" separator and the closing brace). The sub-messages
  between them stay in the text and are translated with the rest of the sentence.
- A quoted section that quotes syntax ('{', '{0}') is a literal and masked whole.
- MessageFormat apostrophes: in a MessageFormat string (the source has "{digit" or "''") a literal
  apostrophe is written ''. The model gets plain apostrophes (Don''t -> Don't), and every apostrophe
  in its output is doubled again before the placeholders go back, so "L'utilisateur {0}" is written
  "L''utilisateur {0}". A single apostrophe would start a quoted section and Java would print "{0}"
  as text. Inside a choice sub-message an apostrophe is '' (ChoiceFormat), or '''' when that
  sub-message has its own arguments (it is formatted again).

The profile is chosen per file: MessageFormat always, plus java_printf (%s, %1$s) and js_template
(${…}) when the source file uses them. Override per source file with `placeholders: [...]`.

`algebras placeholders` adds mf_arg_quoted (an argument inside a quoted section), mf_apostrophe (a
single apostrophe that Java would drop) and mf_type_changed ({0,number} -> {0,число}). Tier-1
repairs: double the single apostrophes, restore the type/style by argument index, and the generic
lookalike/unique-slot repair. Fixes are written in place, keeping comments, order and continuation
lines.
"""

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple

from algebras.services.placeholders.engine import (
    _TOKEN_RE,
    Masked,
    Placeholder,
    Problem,
    repair,
    token,
    verify,
)
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.profiles import (
    PlaceholderProfile,
    detect_profile,
    profile_for_path,
    register_profile_resolver,
)
from algebras.services.placeholders.syntaxes import PRINTF, SYNTAXES, Syntax

_EXTENSIONS = [".properties"]
MF = "messageformat"

# ---------------------------------------------------------------------------
# Lenient MessageFormat scanner
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Piece:
    start: int
    end: int
    role: str  # arg | quote | choice_open | choice_sep | choice_close
    depth: int  # 0 = top level, 1 = inside a choice sub-message, …
    index: Optional[str] = None  # argument index or name (arg, choice_open)


# Argument index or name. Unicode digits/letters and spaces are accepted so that damaged arguments
# ({ 0 }, {٠}, {имя}) are still found, reported and repaired.
_NAME = re.compile(r"\s*([\w.]+)\s*")
_TYPE = re.compile(r"\s*([^\s,{}']+)\s*")
_LIMIT = re.compile(r"\s*(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|[-+]?∞)\s*[#<≤]")


class _Scanner:
    def __init__(self, text: str, quotes: Optional[Set[str]] = None):
        self.t = text
        self.n = len(text)
        # When set, only these quoted sections count as intentional quotes; any other apostrophe
        # is a literal one (used to repair a target against its source).
        self.quotes = quotes

    def scan(self) -> List[Piece]:
        pieces: List[Piece] = []
        self.message(0, 0, False, pieces)
        return pieces

    def _quote_end(self, p: int) -> int:
        """`p` is after the opening quote; index after the closing one, or -1 if unclosed."""
        t = self.t
        while p < self.n:
            if t[p] == "'":
                if p + 1 < self.n and t[p + 1] == "'":
                    p += 2
                    continue
                return p + 1
            p += 1
        return -1

    def message(self, pos: int, depth: int, in_choice: bool, out: List[Piece]) -> int:
        t = self.t
        while pos < self.n:
            c = t[pos]
            if c == "'":
                run = pos
                while run < self.n and t[run] == "'":
                    run += 1
                if run - pos >= 2:  # '' (or '''' in a choice): escaped apostrophes
                    pos = run
                    continue
                nxt = t[run] if run < self.n else ""
                if nxt in ("{", "}") or (in_choice and nxt == "|"):
                    end = self._quote_end(pos + 1)
                    if end > 0 and (self.quotes is None or t[pos:end] in self.quotes):
                        out.append(Piece(pos, end, "quote", depth))
                        pos = end
                        continue
                pos += 1  # a literal apostrophe
            elif c == "{":
                found: List[Piece] = []
                end = self.argument(pos, depth, found)
                if end < 0:
                    pos += 1
                else:
                    out.extend(found)
                    pos = end
            elif in_choice and c in "|}":
                return pos
            else:
                pos += 1
        return pos

    def _style_end(self, p: int) -> int:
        """Index of the brace closing an argument whose style starts at `p` (Java in-brace rules)."""
        t = self.t
        depth = 0
        in_quote = False
        while p < self.n:
            c = t[p]
            if in_quote:
                if c == "'":
                    in_quote = False
            elif c == "'":
                in_quote = True
            elif c == "{":
                depth += 1
            elif c == "}":
                if depth == 0:
                    return p
                depth -= 1
            p += 1
        return -1

    def argument(self, start: int, depth: int, out: List[Piece]) -> int:
        """Parse an argument at `start` ("{"); append its pieces and return its end, or -1."""
        t = self.t
        m = _NAME.match(t, start + 1)
        if not m:
            return -1
        index = m.group(1)
        p = m.end()
        if p >= self.n:
            return -1
        if t[p] == "}":
            out.append(Piece(start, p + 1, "arg", depth, index))
            return p + 1
        if t[p] != ",":
            return -1
        tm = _TYPE.match(t, p + 1)
        if not tm:
            return -1
        p = tm.end()
        if p >= self.n:
            return -1
        if t[p] == "}":
            out.append(Piece(start, p + 1, "arg", depth, index))
            return p + 1
        if t[p] != ",":
            return -1
        if tm.group(1).lower() == "choice":
            end = self.choice(start, p + 1, depth, index, out)
            if end > 0:
                return end
            out.clear()
        close = self._style_end(p + 1)
        if close < 0:
            return -1
        out.append(Piece(start, close + 1, "arg", depth, index))  # masked whole
        return close + 1

    def choice(self, start: int, p: int, depth: int, index: str, out: List[Piece]) -> int:
        t = self.t
        lm = _LIMIT.match(t, p)
        if not lm:
            return -1
        out.append(Piece(start, lm.end(), "choice_open", depth, index))
        pos = lm.end()
        while True:
            pos = self.message(pos, depth + 1, True, out)
            if pos >= self.n:
                return -1
            if t[pos] == "}":
                out.append(Piece(pos, pos + 1, "choice_close", depth))
                return pos + 1
            lm = _LIMIT.match(t, pos + 1)  # t[pos] == "|"
            if not lm:
                return -1
            out.append(Piece(pos, lm.end(), "choice_sep", depth))
            pos = lm.end()


def scan(text: str, quotes: Optional[Set[str]] = None) -> List[Piece]:
    """MessageFormat pieces of `text`, in text order, without overlaps."""
    if not isinstance(text, str) or "{" not in text and "'" not in text:
        return []
    return _Scanner(text, quotes).scan()


def is_messageformat(text: str) -> bool:
    """A MessageFormat pattern: it has a numbered argument or an escaped apostrophe."""
    return isinstance(text, str) and (re.search(r"\{\s*\d", text) is not None or "''" in text)


def _norm_index(index: Optional[str]) -> str:
    if index is None:
        return ""
    return "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in index)


def _arg_index(raw: str) -> Optional[str]:
    m = re.match(r"\{\s*([\w.]+)", raw)
    return _norm_index(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Syntaxes, codec and profile
# ---------------------------------------------------------------------------


class _Match:
    def __init__(self, raw: str, start: int, end: int):
        self._raw, self._start, self._end = raw, start, end

    def group(self, index: int = 0) -> str:
        return self._raw

    def start(self) -> int:
        return self._start

    def end(self) -> int:
        return self._end


class _MessageFormatPattern:
    """Duck-typed stand-in for a compiled regex (the engine only calls finditer)."""

    pattern = MF

    def finditer(self, text: str) -> Iterator[_Match]:
        for p in scan(text):
            yield _Match(text[p.start : p.end], p.start, p.end)


def _roles(pieces: Sequence[Piece], placeholders: Sequence[Placeholder]) -> List[str]:
    by_span = {(p.start, p.end): p.role for p in pieces}
    return [by_span.get((ph.start, ph.end), "other") for ph in placeholders]


def _transform(text: str, roles: Sequence[str], collapse: bool) -> str:
    """
    Un-double (collapse) or double the apostrophes in the literal text of a masked string. The
    factor is 2 at the top level and in a choice sub-message, 4 in a sub-message that has its own
    arguments (ChoiceFormat removes one level of quoting, MessageFormat the next).
    """
    items: List[Tuple[str, str]] = []  # (kind, text): kind is "lit" or a token role
    pos = 0
    for m in _TOKEN_RE.finditer(text):
        items.append(("lit", text[pos : m.start()]))
        i = int(m.group(1))
        items.append((roles[i] if i < len(roles) else "other", m.group(0)))
        pos = m.end()
    items.append(("lit", text[pos:]))

    stack: List[int] = []  # current sub-message ids
    nested: Dict[int, bool] = {}
    owner: List[Optional[int]] = []
    for kind, _ in items:
        if kind == "lit":
            owner.append(stack[-1] if stack else None)
            continue
        owner.append(None)
        if kind in ("arg", "quote", "choice_open") and stack:
            nested[stack[-1]] = True
        if kind == "choice_open":
            stack.append(len(nested))
            nested[stack[-1]] = False
        elif kind == "choice_sep" and stack:
            stack[-1] = len(nested)
            nested[stack[-1]] = False
        elif kind == "choice_close" and stack:
            stack.pop()

    out: List[str] = []
    for (kind, chunk), sub in zip(items, owner):
        if kind != "lit":
            out.append(chunk)
            continue
        factor = 4 if sub is not None and nested.get(sub) else 2
        if collapse:
            out.append(re.sub(r"'+", lambda m: "'" * math.ceil(len(m.group(0)) / factor), chunk))
        else:
            out.append(re.sub(r"'+", lambda m: "'" * (len(m.group(0)) * factor), chunk))
    return "".join(out)


def _encode(masked: Masked) -> str:
    if not is_messageformat(masked.source):
        return masked.text
    return _transform(masked.text, _roles(scan(masked.source), masked.placeholders), collapse=True)


def _decode(translated: str, masked: Masked) -> str:
    if not is_messageformat(masked.source):
        return translated
    return _transform(translated, _roles(scan(masked.source), masked.placeholders), collapse=False)


def _type_changes(source: str, target: str, problems: List[Problem]) -> List[Problem]:
    """
    {0,number} -> {0,число} (or {0,number,#,##}): one mf_type_changed instead of missing + extra.
    Used by `algebras placeholders`; verify() (translation gate, healthcheck) keeps missing + extra.
    """
    src_args = {source[p.start : p.end] for p in scan(source) if p.role == "arg"}
    tgt_args = {target[p.start : p.end] for p in scan(target) if p.role == "arg"}
    missing = [p for p in problems if p.code == "missing" and p.placeholder in src_args]
    extra = [p for p in problems if p.code == "extra" and p.placeholder in tgt_args]
    if not missing or not extra:
        return problems
    replaced: Dict[int, Problem] = {}
    dropped: Set[int] = set()
    for e in extra:
        index = _arg_index(e.placeholder)
        m = next((m for m in missing if id(m) not in dropped and _arg_index(m.placeholder) == index), None)
        if m is None or index is None:
            continue
        dropped.add(id(m))
        replaced[id(e)] = Problem(
            "mf_type_changed",
            e.placeholder,
            f"Argument {e.placeholder} has a different format than the source {m.placeholder}; "
            "the type and style are never translated",
        )
    return [replaced.get(id(p), p) for p in problems if id(p) not in dropped]


MESSAGEFORMAT = Syntax(
    name=MF,
    kind="named",
    pattern=_MessageFormatPattern(),  # type: ignore[arg-type]
    # Fullwidth braces or a damaged argument that the scanner does not take for one.
    lenient=re.compile(r"[{｛]\s*[\w.]+\s*(?:[,，][^{}｛｝]*)?[}｝]"),
    encode=_encode,
    decode=_decode,
)
JAVA_PRINTF = Syntax(name="java_printf", kind="printf", pattern=PRINTF.pattern, lenient=PRINTF.lenient)

for _syntax in (MESSAGEFORMAT, JAVA_PRINTF):
    SYNTAXES.setdefault(_syntax.name, _syntax)

PROPERTIES_PROFILE = PlaceholderProfile(name="properties", syntax_names=(MF, "java_printf", "js_template"))


def resolve_profile(file_path: str, config=None) -> PlaceholderProfile:
    """MessageFormat always; java_printf and ${…} only if the source file uses them."""
    from algebras.utils.properties_handler import read_properties_file

    try:
        values = list(read_properties_file(file_path).values())
    except Exception:
        return PROPERTIES_PROFILE
    return detect_profile(values, candidates=("java_printf", "js_template"), name="properties", always=(MF,))


# ---------------------------------------------------------------------------
# Check and repair
# ---------------------------------------------------------------------------


def _source_quotes(source: str) -> Set[str]:
    return {source[p.start : p.end] for p in scan(source) if p.role == "quote"}


def _java_visible(text: str) -> Set[str]:
    """Indexes of top-level arguments that Java's MessageFormat actually sees (not inside '…')."""
    visible: Set[str] = set()
    scanner = _Scanner(text)
    pos, in_quote = 0, False
    while pos < len(text):
        c = text[pos]
        if c == "'":
            if pos + 1 < len(text) and text[pos + 1] == "'":
                pos += 2
                continue
            in_quote = not in_quote
        elif c == "{" and not in_quote:
            found: List[Piece] = []
            end = scanner.argument(pos, 0, found)
            if end > 0:
                visible.add(_norm_index(found[0].index))
                pos = end
                continue
        pos += 1
    return visible


def fix_apostrophes(source: str, target: str) -> str:
    """Double every single apostrophe of the target's literal text (quotes the source has are kept)."""
    pieces = scan(target, _source_quotes(source))
    parts: List[str] = []
    pos = 0
    for i, p in enumerate(pieces):
        parts.append(target[pos : p.start])
        parts.append(token(i))
        pos = p.end
    parts.append(target[pos:])
    roles = [p.role for p in pieces]
    text = _transform(_transform("".join(parts), roles, collapse=True), roles, collapse=False)
    return _TOKEN_RE.sub(lambda m: target[pieces[int(m.group(1))].start : pieces[int(m.group(1))].end], text)


def apostrophe_problems(source: str, target: str) -> List[Problem]:
    """mf_arg_quoted / mf_apostrophe for a MessageFormat source."""
    if not is_messageformat(source) or not isinstance(target, str):
        return []
    src_indexes = {_norm_index(p.index) for p in scan(source) if p.depth == 0 and p.role in ("arg", "choice_open")}
    tgt_pieces = [p for p in scan(target, _source_quotes(source)) if p.depth == 0 and p.role in ("arg", "choice_open")]
    visible = _java_visible(target)
    problems = [
        Problem(
            "mf_arg_quoted",
            target[p.start : p.end],
            f"{target[p.start:p.end]} is inside a quoted section ('…'), so Java prints it as text; "
            "write a literal apostrophe as ''",
        )
        for p in tgt_pieces
        if _norm_index(p.index) in src_indexes and _norm_index(p.index) not in visible
    ]
    if not problems and fix_apostrophes(source, target) != target:
        problems.append(
            Problem("mf_apostrophe", "'", "Single apostrophe in a MessageFormat string: Java drops it; write it as ''")
        )
    return problems


def value_problems(source: str, target: str, profile: PlaceholderProfile) -> List[Problem]:
    problems = verify(source, target, profile)
    if MF not in profile.syntax_names:
        return problems
    problems = _type_changes(source, target, problems)
    quoted = apostrophe_problems(source, target)
    if any(p.code == "mf_arg_quoted" for p in quoted):
        # The quote that swallows the argument also shows up as missing/extra placeholders.
        swallowed = {p.placeholder for p in quoted}
        problems = [
            p
            for p in problems
            if not (p.code == "missing" and p.placeholder in swallowed)
            and not (p.code == "extra" and p.placeholder.startswith("'"))
        ]
    return problems + quoted


def _restore_types(source: str, target: str) -> str:
    """Put the source's {n,type,style} back on target arguments with the same index."""
    by_index: Dict[str, Set[str]] = {}
    for p in scan(source):
        if p.role == "arg":
            by_index.setdefault(_norm_index(p.index), set()).add(source[p.start : p.end])
    edits: List[Tuple[int, int, str]] = []
    for p in scan(target):
        raw = target[p.start : p.end]
        want = by_index.get(_norm_index(p.index))
        if p.role == "arg" and want and raw not in want and len(want) == 1:
            edits.append((p.start, p.end, next(iter(want))))
    for start, end, raw in reversed(edits):
        target = target[:start] + raw + target[end:]
    return target


def repair_value(source: str, target: str, profile: PlaceholderProfile) -> Optional[str]:
    """Tier-1 fix without the API, or None when it cannot be fixed this way (or needs no fix)."""
    fixed = target
    if MF in profile.syntax_names:
        # Apostrophes first: a stray quote hides arguments, which the generic repair would
        # otherwise take for damaged placeholders.
        if is_messageformat(source):
            fixed = fix_apostrophes(source, fixed)
        fixed = _restore_types(source, fixed)
    generic = repair(source, fixed, profile)
    if generic is not None:
        fixed = generic
    if fixed == target or value_problems(source, fixed, profile):
        return None
    return fixed


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    from algebras.utils.properties_handler import read_properties_file

    source = read_properties_file(source_file)
    target = read_properties_file(target_file)
    profile = profile_for_path(source_file, config)
    findings: List[Finding] = []
    for key, source_text in source.items():
        target_text = target.get(key)
        if not isinstance(target_text, str) or not target_text.strip():
            continue  # untranslated: 'status' reports it
        problems = value_problems(source_text, target_text, profile)
        if problems:
            fixed = repair_value(source_text, target_text, profile)
            findings.append(Finding(key, source_text, target_text, problems, path=(key,), fixed=fixed))
    return findings


def write_fixes(target_file: str, fixes: Dict[Tuple[str, ...], str], language: Optional[str] = None, config=None) -> None:
    """Replace the fixed values in place; comments, order and continuation lines stay as they are."""
    from algebras.utils.properties_handler import update_properties_values

    missing = update_properties_values(target_file, {path[0]: value for path, value in fixes.items()}, add_missing=False)
    if missing:
        raise ValueError(f"Could not find {', '.join(missing)} in {target_file}")


register_profile_resolver(_EXTENSIONS, resolve_profile)
register_file_check(_EXTENSIONS, check_file)
register_fix_writer(_EXTENSIONS, write_fixes)
