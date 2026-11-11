"""
Flutter ARB (.arb): ICU MessageFormat placeholders.

- Simple arguments: {name}, {count}, {amount, number, compact}, {date, date, yMd}.
- plural / select / selectordinal: the argument name, the type and the branch keywords are syntax.
  `#` in a plural branch is the count. Branch text is translatable.
- ICU quoting: '{' and '}' are literal braces, '' is an apostrophe. Quoted text is never an argument.
- `@key.placeholders` metadata lists the argument names of a key; it is never translated.

During translation ICUMessageService splits plural/select messages first, so the model only gets
the branch text, with any arguments inside masked as tokens. The `arb_icu` syntax below finds
arguments with a small, lenient ICU scanner instead of a regex, so branch text ("one{item}") is
never taken for an argument and quoted braces are skipped.

`algebras placeholders` compares every message structurally (codes: icu_unparseable,
icu_arg_renamed, icu_type_changed, icu_keyword_changed, missing, extra) and repairs renamed
arguments, changed types and translated branch keywords in place.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple, Union

from algebras.services.placeholders.engine import Problem, _normalizations, repair, verify
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.profiles import PlaceholderProfile, profile_for_path, register_profile
from algebras.services.placeholders.syntaxes import SYNTAXES, Syntax

COMPLEX_TYPES = frozenset({"plural", "select", "selectordinal"})

# ---------------------------------------------------------------------------
# Lenient ICU scanner
# ---------------------------------------------------------------------------

Span = Tuple[int, int]


@dataclass
class IcuHash:
    start: int


@dataclass
class IcuOption:
    keyword: str
    span: Span
    body: List["IcuNode"]


@dataclass
class IcuArg:
    name: str
    name_span: Span
    start: int
    end: int  # after the closing brace
    head_end: int  # after the type (or the name, for {name})
    type: Optional[str] = None
    type_span: Optional[Span] = None
    style: Optional[str] = None
    style_span: Optional[Span] = None
    options: List[IcuOption] = field(default_factory=list)

    @property
    def is_complex(self) -> bool:
        return bool(self.options)


IcuNode = Union[IcuArg, IcuHash]

_WORD = re.compile(r"[^\s{}',#]+")
_KEYWORD = re.compile(r"[^\s{}]+")
_OFFSET = re.compile(r"offset\s*:\s*\d+")


class _Scanner:
    """
    Finds ICU arguments with their exact spans. Lenient on purpose: transliterated names, types and
    keywords ("{счёт, множественное, другое{…}}") are still recognized, so they can be reported
    and repaired. A brace that does not start a well-formed argument is treated as text.
    """

    def __init__(self, text: str):
        self.t = text
        self.n = len(text)
        self.quotes: List[Span] = []  # top-level quoted literals such as '{' or '{name}'

    def _ws(self, p: int) -> int:
        while p < self.n and self.t[p].isspace():
            p += 1
        return p

    def _quote_end(self, p: int) -> int:
        """`p` is just after an opening quote; return the index after the closing one."""
        while p < self.n:
            if self.t[p] == "'":
                if p + 1 < self.n and self.t[p + 1] == "'":
                    p += 2
                    continue
                return p + 1
            p += 1
        return self.n

    def message(self, pos: int, depth: int, plural: bool) -> Tuple[List[IcuNode], int]:
        nodes: List[IcuNode] = []
        t = self.t
        while pos < self.n:
            c = t[pos]
            if c == "'":
                nxt = t[pos + 1] if pos + 1 < self.n else ""
                if nxt == "'":
                    pos += 2
                elif nxt in ("{", "}") or (plural and nxt == "#"):
                    end = self._quote_end(pos + 1)
                    if depth == 0:
                        self.quotes.append((pos, end))
                    pos = end
                else:
                    pos += 1
            elif c == "{":
                arg = self.argument(pos, depth)
                if arg is None:
                    pos += 1
                else:
                    nodes.append(arg)
                    pos = arg.end
            elif c == "}":
                if depth > 0:
                    return nodes, pos
                pos += 1
            elif c == "#" and plural:
                nodes.append(IcuHash(pos))
                pos += 1
            else:
                pos += 1
        return nodes, pos

    def argument(self, start: int, depth: int) -> Optional[IcuArg]:
        t = self.t
        p = self._ws(start + 1)
        m = _WORD.match(t, p)
        if not m:
            return None
        arg = IcuArg(name=m.group(0), name_span=m.span(), start=start, end=-1, head_end=m.end())
        p = self._ws(m.end())
        if p >= self.n:
            return None
        if t[p] == "}":
            arg.end = p + 1
            return arg
        if t[p] != ",":
            return None
        p = self._ws(p + 1)
        m = _WORD.match(t, p)
        if not m:
            return None
        arg.type, arg.type_span, arg.head_end = m.group(0), m.span(), m.end()
        p = self._ws(m.end())
        if p >= self.n:
            return None
        if t[p] == "}":
            arg.end = p + 1
            return arg
        if t[p] != ",":
            return None
        p += 1

        q = self._ws(p)
        offset = _OFFSET.match(t, q)
        if offset:
            q = self._ws(offset.end())
        kw = _KEYWORD.match(t, q)
        if kw and self._ws(kw.end()) < self.n and t[self._ws(kw.end())] == "{":
            plural = arg.type.lower() != "select"
            while True:
                q = self._ws(q)
                if q >= self.n:
                    return None
                if t[q] == "}":
                    arg.end = q + 1
                    return arg if arg.options else None
                kw = _KEYWORD.match(t, q)
                if not kw:
                    return None
                b = self._ws(kw.end())
                if b >= self.n or t[b] != "{":
                    return None
                body, close = self.message(b + 1, depth + 1, plural)
                if close >= self.n or t[close] != "}":
                    return None
                arg.options.append(IcuOption(kw.group(0), kw.span(), body))
                q = close + 1

        # A style ("compact", "yMd", "::currency/EUR"): plain text up to the closing brace.
        close = t.find("}", p)
        if close < 0 or "{" in t[p:close]:
            return None
        raw = t[p:close]
        lead = len(raw) - len(raw.lstrip())
        arg.style = raw.strip()
        arg.style_span = (p + lead, p + lead + len(arg.style))
        arg.end = close + 1
        return arg


def scan_with_quotes(text: str) -> Tuple[List[IcuNode], List[Span]]:
    """Top-level ICU nodes of `text` (arguments, and # only inside plural branches) and quoted braces."""
    if not isinstance(text, str) or ("{" not in text and "}" not in text):
        return [], []
    scanner = _Scanner(text)
    nodes, _ = scanner.message(0, 0, False)
    return nodes, scanner.quotes


def scan(text: str) -> List[IcuNode]:
    return scan_with_quotes(text)[0]


def walk(nodes: Sequence[IcuNode]) -> Iterator[IcuArg]:
    """Every argument, nested ones included, in text order."""
    for node in nodes:
        if isinstance(node, IcuArg):
            yield node
            for option in node.options:
                yield from walk(option.body)


# ---------------------------------------------------------------------------
# Placeholder syntax backed by the scanner
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


def _signature(name: str, args: Sequence[IcuArg]) -> str:
    typed = sorted({(a.type, a.style or "") for a in args if a.type})
    if not typed:
        return "{" + name + "}"
    return "{" + name + ", " + "; ".join(f"{t}, {s}" if s else t for t, s in typed) + "}"


class _ArbArgumentPattern:
    """
    Duck-typed stand-in for a compiled regex (the engine only calls finditer).

    - Plain messages: every argument and every quoted brace ('{', '{name}'), with its exact text, so
      it is masked and put back byte for byte (a lost quote would turn literal text into an argument).
    - plural/select messages: one entry per argument name ({count, plural}, {name}), spanning only
      the argument head. Target branches may legitimately repeat an argument (ru adds few/many),
      so names and types are compared, not counts; branch keywords are checked by the file check.
    """

    pattern = "arb_icu"

    def finditer(self, text: str) -> Iterator[_Match]:
        nodes, quotes = scan_with_quotes(text)
        args = list(walk(nodes))
        if not any(a.is_complex for a in args):
            spans = sorted([(a.start, a.end) for a in args] + quotes)
            for start, end in spans:
                yield _Match(text[start:end], start, end)
            return
        by_name: Dict[str, List[IcuArg]] = {}
        for a in args:
            by_name.setdefault(a.name, []).append(a)
        for name, group in by_name.items():
            first = group[0]
            yield _Match(_signature(name, group), first.start, first.head_end)


ARB_ICU = Syntax(name="arb_icu", kind="named", pattern=_ArbArgumentPattern())  # type: ignore[arg-type]
SYNTAXES.setdefault(ARB_ICU.name, ARB_ICU)

ARB_PROFILE = PlaceholderProfile(name="arb", syntax_names=("arb_icu",))

_EXTENSIONS = [".arb"]


# ---------------------------------------------------------------------------
# Structural check
# ---------------------------------------------------------------------------


def _parse_error(text: str) -> Optional[str]:
    from pyicumessageformat import Parser

    try:
        Parser().parse(text)
        return None
    except Exception as e:  # pyicumessageformat raises SyntaxError and friends
        return str(e) or type(e).__name__


def _complex_args(nodes: Sequence[IcuNode]) -> List[IcuArg]:
    return [a for a in walk(nodes) if a.is_complex]


def _typed(args: Iterable[IcuArg], name: str) -> Set[Tuple[str, str]]:
    return {(a.type, a.style or "") for a in args if a.name == name and a.type}


def _allowed_keywords(source: IcuArg, target_language: str) -> Set[str]:
    from algebras.utils.plural_rules import PLURAL_CATEGORY_ORDER, get_plural_categories

    allowed = {o.keyword for o in source.options}
    if (source.type or "").lower() == "plural":
        allowed |= set(get_plural_categories(target_language))
    elif (source.type or "").lower() == "selectordinal":
        allowed |= set(PLURAL_CATEGORY_ORDER)
    return allowed


def _keyword_ok(keyword: str, allowed: Set[str], source: IcuArg) -> bool:
    if keyword in allowed:
        return True
    # Explicit-value branches (=0, =1 …) may be added in plural messages.
    return (source.type or "").lower() != "select" and re.fullmatch(r"=\d+", keyword) is not None


def _branch_names(body: Sequence[IcuNode], selector: str) -> Set[str]:
    names: Set[str] = set()
    for node in body:
        if isinstance(node, IcuHash):
            names.add(selector)
        else:
            names.add(node.name)
            for option in node.options:
                names |= _branch_names(option.body, selector)
    return names


def _single_count(keyword: str, target_language: str) -> bool:
    from algebras.utils.plural_rules import covers_single_count

    return keyword.startswith("=") or covers_single_count(target_language, keyword)


def _pair_complex(source: List[IcuArg], target: List[IcuArg], rename: Dict[str, str]) -> List[Tuple[IcuArg, IcuArg]]:
    """Pair plural/select arguments by (repaired) name, falling back to their order."""
    pairs = []
    used: Set[int] = set()
    for i, s in enumerate(source):
        match = next(
            (j for j, t in enumerate(target) if j not in used and rename.get(t.name, t.name) == s.name), None
        )
        if match is None and len(source) == len(target) and i not in used:
            match = i
        if match is not None:
            used.add(match)
            pairs.append((s, target[match]))
    return pairs


def _lost_keywords(source: IcuArg, target: IcuArg, target_language: str) -> List[str]:
    """Source branches the target dropped although its language needs them."""
    from algebras.utils.plural_rules import get_plural_categories

    present = {o.keyword for o in target.options}
    kind = (source.type or "").lower()
    needed = set(get_plural_categories(target_language)) if kind == "plural" else {"other"}
    return [
        o.keyword
        for o in source.options
        if o.keyword not in present
        and (kind == "select" or o.keyword.startswith("=") or o.keyword in needed)
    ]


def message_problems(
    source: str,
    target: str,
    target_language: str,
    declared: Sequence[str] = (),
) -> List[Problem]:
    """
    Structural problems of an ICU target message compared with its source. `declared` are the
    names from `@key.placeholders`; they count as known argument names.
    """
    if not isinstance(target, str) or not target.strip() or _parse_error(source) is not None:
        return []
    problems: List[Problem] = []
    error = _parse_error(target)
    if error is not None:
        problems.append(Problem("icu_unparseable", "", f"Not a valid ICU message: {error}"))

    src_nodes, tgt_nodes = scan(source), scan(target)
    src_args, tgt_args = list(walk(src_nodes)), list(walk(tgt_nodes))
    src_names = [a.name for a in src_args]
    known = set(src_names) | set(declared)
    tgt_names = {a.name for a in tgt_args}
    unknown = sorted(n for n in tgt_names if n not in known)
    missing = [n for n in dict.fromkeys(src_names) if n not in tgt_names]

    for name in unknown:
        if missing:
            problems.append(
                Problem(
                    "icu_arg_renamed",
                    "{" + name + "}",
                    f"Argument {{{name}}} is not in the source (expected {', '.join('{' + m + '}' for m in missing)}); "
                    "argument names are never translated",
                )
            )
        else:
            problems.append(Problem("extra", "{" + name + "}", f"Argument {{{name}}} is not in the source"))
    if not unknown:
        for name in missing:
            problems.append(Problem("missing", "{" + name + "}", f"Missing argument {{{name}}}"))

    for name in dict.fromkeys(src_names):
        if name not in tgt_names:
            continue
        want, got = _typed(src_args, name), _typed(tgt_args, name)
        if want != got:
            problems.append(
                Problem(
                    "icu_type_changed",
                    "{" + name + "}",
                    f"Argument {{{name}}} has type {_fmt_types(got)}, source has {_fmt_types(want)}",
                )
            )

    # Quoted literal braces ('{', '{name}') must survive as they are.
    problems.extend(p for p in verify(source, target, ARB_PROFILE) if p.placeholder.startswith("'"))

    for s, t in _pair_complex(_complex_args(src_nodes), _complex_args(tgt_nodes), {}):
        allowed = _allowed_keywords(s, target_language)
        bad = [o.keyword for o in t.options if not _keyword_ok(o.keyword, allowed, s)]
        lost = _lost_keywords(s, t, target_language)
        if bad or lost:
            details = []
            if bad:
                details.append(f"unknown branch keyword(s) {', '.join(bad)}")
            if lost:
                details.append(f"missing branch(es) {', '.join(lost)}")
            problems.append(
                Problem("icu_keyword_changed", " ".join(bad + lost), f"{{{s.name}, {s.type}}}: " + "; ".join(details))
            )

        # Every target branch keeps the arguments of the branch it is translated from.
        src_options = {o.keyword: o for o in s.options}
        for option in t.options:
            base = src_options.get(option.keyword) or src_options.get("other")
            if base is None:
                continue
            need = _branch_names(base.body, s.name) - set(missing)
            have = _branch_names(option.body, t.name)
            lacking = sorted(need - have)
            if s.name in lacking and (s.type or "").lower() != "select" and _single_count(option.keyword, target_language):
                lacking.remove(s.name)  # "one{Ein Element}" may name its single count in words
            for name in lacking:
                problems.append(
                    Problem(
                        "missing",
                        "{" + name + "}",
                        f"Branch '{option.keyword}' of {{{s.name}, {s.type}}} lacks {{{name}}}"
                        + (" (or #)" if name == s.name else ""),
                    )
                )
    return problems


def _fmt_types(types: Set[Tuple[str, str]]) -> str:
    if not types:
        return "none"
    return ", ".join(f"{t} {s}".strip() for t, s in sorted(types))


# ---------------------------------------------------------------------------
# Deterministic repair
# ---------------------------------------------------------------------------


def repair_message(
    source: str,
    target: str,
    target_language: str,
    declared: Sequence[str] = (),
) -> Optional[str]:
    """
    Fix a damaged ICU target without the API: renamed argument names (lookalike mapping, then a
    unique slot), changed argument types/styles, and translated branch keywords (by branch position,
    or a last branch back to `other`). Returns None when the result would still have problems.
    """
    if not message_problems(source, target, target_language, declared):
        return None

    src_nodes, tgt_nodes = scan(source), scan(target)
    src_args, tgt_args = list(walk(src_nodes)), list(walk(tgt_nodes))
    src_names = list(dict.fromkeys(a.name for a in src_args))
    known = set(src_names) | set(declared)
    tgt_names = list(dict.fromkeys(a.name for a in tgt_args))
    unknown = [n for n in tgt_names if n not in known]
    missing = [n for n in src_names if n not in tgt_names]

    rename: Dict[str, str] = {}
    for name in list(unknown):
        candidates = {c for c in _normalizations(name) if c in missing}
        if len(candidates) == 1:
            fixed = candidates.pop()
            rename[name] = fixed
            unknown.remove(name)
            missing.remove(fixed)
    if len(unknown) == 1 and len(missing) == 1:
        rename[unknown[0]] = missing[0]

    edits: Dict[Span, str] = {}
    for a in tgt_args:
        if a.name in rename:
            edits[a.name_span] = rename[a.name]

    # Types and styles, by (repaired) name, when the source uses exactly one type for that name.
    for a in tgt_args:
        name = rename.get(a.name, a.name)
        want = _typed(src_args, name)
        if len(want) != 1 or not a.type:
            continue
        want_type, want_style = next(iter(want))
        if a.type != want_type and a.type_span:
            edits[a.type_span] = want_type
        if (a.style or "") != want_style and a.style_span and want_style and not a.is_complex:
            edits[a.style_span] = want_style

    # Branch keywords.
    for s, t in _pair_complex(_complex_args(src_nodes), _complex_args(tgt_nodes), rename):
        allowed = _allowed_keywords(s, target_language)
        present = {o.keyword for o in t.options}
        for i, option in enumerate(t.options):
            if _keyword_ok(option.keyword, allowed, s):
                continue
            replacement = None
            if len(t.options) == len(s.options) and s.options[i].keyword not in present:
                replacement = s.options[i].keyword
            elif i == len(t.options) - 1 and "other" not in present:
                replacement = "other"
            if replacement is not None:
                edits[option.span] = replacement
                present.add(replacement)

    if not edits:
        # Plain messages: the generic lookalike / unique-slot repair (e.g. a damaged quoted '{').
        fixed = repair(source, target, ARB_PROFILE)
        if fixed is None or message_problems(source, fixed, target_language, declared):
            return None
        return fixed
    fixed = target
    for (start, end), value in sorted(edits.items(), reverse=True):
        fixed = fixed[:start] + value + fixed[end:]
    if message_problems(source, fixed, target_language, declared):
        return None
    return fixed


# ---------------------------------------------------------------------------
# File check and fix writer
# ---------------------------------------------------------------------------


def declared_placeholders(arb: Dict, key: str) -> List[str]:
    """Names in `@key.placeholders`, the authoritative argument list of a key."""
    meta = arb.get(f"@{key}")
    placeholders = meta.get("placeholders") if isinstance(meta, dict) else None
    return list(placeholders) if isinstance(placeholders, dict) else []


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    """Placeholder findings for a target .arb; `@` metadata entries are not translatable and skipped."""
    from algebras.utils.arb_handler import read_arb_file

    source = read_arb_file(source_file)
    target = read_arb_file(target_file)
    profile = profile_for_path(source_file, config)
    findings: List[Finding] = []
    for key, source_text in source.items():
        if key.startswith("@") or not isinstance(source_text, str):
            continue
        target_text = target.get(key)
        if not isinstance(target_text, str) or not target_text.strip():
            continue  # untranslated: 'status' reports it
        if profile.name == ARB_PROFILE.name:
            declared = declared_placeholders(source, key)
            problems = message_problems(source_text, target_text, target_language, declared)
            fixed = repair_message(source_text, target_text, target_language, declared) if problems else None
        else:  # per-file `placeholders:` override in the config
            problems = verify(source_text, target_text, profile)
            fixed = repair(source_text, target_text, profile) if problems else None
        if problems:
            findings.append(Finding(key, source_text, target_text, problems, path=(key,), fixed=fixed))
    return findings


def write_fixes(target_file: str, fixes: Dict[Tuple[str, ...], str], language: Optional[str] = None, config=None) -> None:
    """Replace the fixed values in place; key order, indentation and `@` metadata stay as they are."""
    from algebras.utils.arb_handler import update_arb_values

    missing = update_arb_values(target_file, {path[0]: value for path, value in fixes.items()}, add_missing=False)
    if missing:
        raise ValueError(f"Could not find {', '.join(missing)} in {target_file}")


register_profile(_EXTENSIONS, ARB_PROFILE)
register_file_check(_EXTENSIONS, check_file)
register_fix_writer(_EXTENSIONS, write_fixes)
