"""
XLIFF (.xlf, .xliff; 1.2 and 2.x, including Angular messages.xlf).

A <source>/<target> is read as a flat string with inline elements as markup (see
algebras/utils/xliff_handler.py). The profile masks:

- xliff_inline (atomic): a standalone element (<x/>, <bx/>, <ex/>, 2.x <ph/>, <sc/>, <ec/>, <sm/>,
  <em/>, <cp/>) or an element whose content is native code (1.2 <ph>, <bpt>, <ept>, <it>, a
  protected <mrk>) is ONE token holding its exact markup, so attributes such as equiv-text or
  disp never reach the model;
- xliff_paired (tag): <g>, <pc>, <mrk> become an open token and a close token; the text between
  them is translated in the same sentence;
- raw-text placeholders some tools put in the text: i18next {{name}}, ICU {name}, printf %s.
  They are enabled for every XLIFF file (a false positive is only masked and put back unchanged);
  a per-file `placeholders:` config list narrows them.

ICU messages ({VAR_PLURAL, plural, =1 {...} other {...}}) are split by ICUMessageService first,
then the inline elements of each literal segment are masked. The flat form keeps ICU syntax
characters out of attribute values so an Angular equiv-text="{{count}}" is not parsed as ICU.

Checks beyond the core: inline elements are compared by (tag, id); a changed attribute is
reported as `inline_attr_changed`, broken pairing or nesting (g/pc/mrk, Angular START_*/CLOSE_*
<x/> pairs, bx/ex, bpt/ept, sc/ec, sm/em) as `inline_nesting_broken`. Fixes are written in place:
only the inner XML of the fixed <target> elements changes, other units keep their state and notes.
"""

import re
import xml.etree.ElementTree as ET
from collections import Counter
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape as _xml_escape

from algebras.services.placeholders.engine import Placeholder, Problem, extract, repair, verify
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import KeyPath, register_fix_writer
from algebras.services.placeholders.profiles import PlaceholderProfile, profile_for_path, register_profile
from algebras.services.placeholders.syntaxes import SYNTAXES, Syntax
from algebras.utils.xliff_handler import (
    INLINE_ATOMIC_PATTERN,
    INLINE_CLOSE_PATTERN,
    INLINE_OPEN_PATTERN,
    build_inline_content,
    decode_flat,
    flat_to_file_xml,
    read_xliff_file,
)

_EXTENSIONS = (".xlf", ".xliff")
_INLINE_SYNTAXES = ("xliff_inline", "xliff_paired")

# ---------------------------------------------------------------------------
# Inline element structure
# ---------------------------------------------------------------------------

_ANGULAR_PAIR = re.compile(r"^(START|CLOSE)_(.+)$")


@lru_cache(maxsize=4096)
def _parse(raw: str) -> Optional[Tuple[str, Tuple[Tuple[str, str], ...], bool]]:
    """(tag, attributes, is_close) for an inline element token, or None."""
    m = re.match(r"</([A-Za-z]+)\s*>$", raw)
    if m:
        return m.group(1), (), True
    m = re.match(r"<([A-Za-z]+)", raw)
    if not m:
        return None
    name = m.group(1)
    markup = raw if raw.endswith("/>") or re.search(r"</%s\s*>$" % name, raw) else raw + f"</{name}>"
    try:
        element = ET.fromstring(markup)
    except ET.ParseError:
        return None
    attrs = tuple((k.rsplit("}", 1)[-1], decode_flat(v)) for k, v in element.attrib.items())
    return name, attrs, False


def _is_inline(p: Placeholder) -> bool:
    return p.syntax in _INLINE_SYNTAXES


def _identity(raw: str) -> Optional[Tuple[str, str]]:
    """(tag, id) of an element token; None for close tags and elements without an id."""
    parsed = _parse(raw)
    if parsed is None or parsed[2]:
        return None
    attrs = dict(parsed[1])
    ident = attrs.get("id") or attrs.get("mid")
    return (parsed[0], ident) if ident else None


def _role(raw: str):
    """('open', key) | ('close_tag', tag) | ('close', key) | None (standalone)."""
    parsed = _parse(raw)
    if parsed is None:
        return None
    tag, attrs, is_close = parsed
    attrs = dict(attrs)
    if is_close:
        return ("close_tag", tag)
    self_closing = raw.endswith("/>")
    if tag in ("g", "pc", "mrk") and not self_closing:
        return ("open", (tag, attrs.get("id") or attrs.get("mid") or ""))
    if tag == "x":
        m = _ANGULAR_PAIR.match(attrs.get("id", ""))
        if m:
            return ("open" if m.group(1) == "START" else "close", ("x", m.group(2)))
    if tag in ("bx", "bpt"):
        return ("open", (tag, attrs.get("rid") or attrs.get("id", "")))
    if tag in ("ex", "ept"):
        return ("close", ({"ex": "bx", "ept": "bpt"}[tag], attrs.get("rid") or attrs.get("id", "")))
    if tag in ("sc", "sm") and attrs.get("isolated") != "yes":
        return ("open", (tag, attrs.get("id", "")))
    if tag in ("ec", "em") and attrs.get("startRef") and attrs.get("isolated") != "yes":
        return ("close", ({"ec": "sc", "em": "sm"}[tag], attrs["startRef"]))
    return None


def _structure(placeholders: Sequence[Placeholder]) -> Tuple[bool, Dict]:
    """(properly paired and nested, {(key, n): enclosing (key, n) or None})."""
    stack: List = []
    parents: Dict = {}
    seen: Counter = Counter()
    ok = True
    for p in placeholders:
        if not _is_inline(p):
            continue
        role = _role(p.raw)
        if role is None:
            continue
        kind, key = role
        if kind == "open":
            seen[key] += 1
            ident = (key, seen[key])
            parents[ident] = stack[-1] if stack else None
            stack.append(ident)
        elif kind == "close_tag":
            if stack and stack[-1][0][0] == key:
                stack.pop()
            else:
                ok = False
        else:
            if stack and stack[-1][0] == key:
                stack.pop()
            else:
                ok = False
    return ok and not stack, parents


def _changed_attributes(source_raw: str, target_raw: str) -> List[str]:
    src = dict(_parse(source_raw)[1])
    tgt = dict(_parse(target_raw)[1])
    return sorted(k for k in set(src) | set(tgt) if src.get(k) != tgt.get(k))


def check_inline(src: List[Placeholder], tgt: List[Placeholder], problems: List[Problem]) -> List[Problem]:
    """verify() hook: attribute changes by (tag, id), pairing and nesting of inline elements."""
    problems = list(problems)

    # A source element missing in the target while the target has the same (tag, id) with other
    # attributes: one inline_attr_changed instead of missing + extra.
    extras = [p for p in problems if p.code == "extra" and _identity(p.placeholder)]
    for missing in [p for p in problems if p.code == "missing" and _identity(p.placeholder)]:
        match = next((e for e in extras if _identity(e.placeholder) == _identity(missing.placeholder)), None)
        if match is None:
            continue
        extras.remove(match)
        problems.remove(missing)
        problems.remove(match)
        tag, ident = _identity(missing.placeholder)
        changed = ", ".join(_changed_attributes(missing.placeholder, match.placeholder))
        problems.append(
            Problem(
                "inline_attr_changed",
                decode_flat(match.placeholder),
                f"<{tag} id=\"{ident}\"> has changed attribute(s) {changed}; "
                f"expected {decode_flat(missing.placeholder)}",
            )
        )

    src_ok, src_parents = _structure(src)
    tgt_ok, tgt_parents = _structure(tgt)
    if src_ok:
        broken = not tgt_ok or (set(src_parents) == set(tgt_parents) and src_parents != tgt_parents)
        if broken:
            problems = [p for p in problems if p.code != "tags_unbalanced"]
            problems.append(
                Problem(
                    "inline_nesting_broken",
                    "",
                    "Inline elements are not paired or nested as in the source",
                )
            )
    return problems


XLIFF_INLINE = Syntax(
    name="xliff_inline",
    kind="atomic",
    pattern=re.compile(INLINE_ATOMIC_PATTERN, re.DOTALL),
    check=check_inline,
)

XLIFF_PAIRED = Syntax(
    name="xliff_paired",
    kind="tag",
    pattern=re.compile(INLINE_OPEN_PATTERN + "|" + INLINE_CLOSE_PATTERN),
    check=check_inline,
)

for _syntax in (XLIFF_INLINE, XLIFF_PAIRED):
    SYNTAXES.setdefault(_syntax.name, _syntax)

XLIFF_PROFILE = PlaceholderProfile(
    name="xliff",
    syntax_names=("xliff_inline", "xliff_paired", "xml_tag", "i18next", "icu_simple", "printf"),
)


# ---------------------------------------------------------------------------
# Write-back gate and repair
# ---------------------------------------------------------------------------


def _aligned_source(source: str, target: str) -> str:
    """
    The source an ICU target is compared with: plural branches the target added for its language
    (ru few/many) are copies of the source 'other', so their inline elements are expected.
    """
    from algebras.services.icu_message_service import align_source_branches

    return align_source_branches(source, target)


def translation_problem(
    source: str, translation: str, profile: PlaceholderProfile = XLIFF_PROFILE
) -> Optional[str]:
    """Why `translation` must not be written as the <target> of `source`; None if it may."""
    if not isinstance(translation, str) or not translation.strip():
        return None
    try:
        build_inline_content(translation)
    except ValueError as e:
        return str(e)
    problems = verify(_aligned_source(source or "", translation), translation, profile)
    if problems:
        return "; ".join(p.message for p in problems)
    return None


def repair_unit(source: str, target: str, profile: PlaceholderProfile = XLIFF_PROFILE) -> Optional[str]:
    """
    Deterministic fix: restore inline elements whose attributes changed (by tag and id), then the
    core repair (lookalike placeholders, a unique corrupted slot such as a changed id).
    Returns the fixed target, or None when it cannot be fixed without retranslating.
    """
    source = _aligned_source(source, target)
    fixed = target
    by_identity: Dict[Tuple[str, str], str] = {}
    for p in extract(source, profile):
        if _is_inline(p) and _identity(p.raw):
            by_identity.setdefault(_identity(p.raw), p.raw)
    source_raws = {p.raw for p in extract(source, profile)}
    for p in sorted(extract(target, profile), key=lambda p: p.start, reverse=True):
        if not _is_inline(p) or p.raw in source_raws:
            continue
        original = by_identity.get(_identity(p.raw)) if _identity(p.raw) else None
        if original is not None:
            fixed = fixed[: p.start] + original + fixed[p.end :]

    if not verify(source, fixed, profile):
        return fixed if fixed != target else None
    repaired = repair(source, fixed, profile)
    if repaired is not None and not verify(source, repaired, profile):
        return repaired
    return None


# ---------------------------------------------------------------------------
# `algebras placeholders`: check and in-place fix writer
# ---------------------------------------------------------------------------


def _units(content: Dict) -> List[Dict]:
    return [u for f in content.get("files", []) for u in f.get("trans-units", []) if u.get("id")]


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    """Compare every translated <target> of the target file with the unit's source text."""
    profile = profile_for_path(source_file, config)
    sources = {u["id"]: u.get("source", "") for u in _units(read_xliff_file(source_file))}
    findings: List[Finding] = []
    for unit in _units(read_xliff_file(target_file)):
        target = unit.get("target") or ""
        if not target.strip():
            continue  # untranslated: 'status' reports it
        source = sources.get(unit["id"], unit.get("source", ""))
        problems = verify(_aligned_source(source, target), target, profile)
        try:
            build_inline_content(target)
        except ValueError as e:
            if not any(p.code == "inline_nesting_broken" for p in problems):
                problems.append(Problem("inline_nesting_broken", "", str(e)))
        if problems:
            findings.append(
                Finding(
                    key=unit["id"],
                    source=decode_flat(source),
                    target=decode_flat(target),
                    problems=problems,
                    path=(unit["id"],),
                    fixed=_decoded(repair_unit(source, target, profile)),
                )
            )
    return findings


def _decoded(value: Optional[str]) -> Optional[str]:
    # Reports show attribute values as written; the writer parses this form just as well.
    return decode_flat(value) if value is not None else None


def _unit_span(text: str, unit_id: str) -> Optional[Tuple[int, int]]:
    for quoted in {unit_id, _xml_escape(unit_id, {'"': "&quot;"})}:
        m = re.search(
            r"<(trans-unit|unit)\b[^>]*?\bid\s*=\s*([\"'])" + re.escape(quoted) + r"\2[^>]*>", text
        )
        if m:
            end = text.find(f"</{m.group(1)}>", m.end())
            return (m.end(), end if end != -1 else len(text))
    return None


_TARGET_RE = re.compile(r"<target\b([^>]*?)(?:/>|>(.*?)</target\s*>)", re.DOTALL)


def write_fixes(target_file: str, fixes: Dict[KeyPath, str], language: str = None, config=None) -> None:
    """Replace only the inner XML of the fixed units' <target> elements; the rest stays byte-identical."""
    with open(target_file, "r", encoding="utf-8") as f:
        text = f.read()
    not_found = []
    for path, value in fixes.items():
        unit_id = path[0]
        span = _unit_span(text, unit_id)
        m = _TARGET_RE.search(text, span[0], span[1]) if span else None
        if m is None:
            not_found.append(unit_id)
            continue
        attrs = m.group(1).rstrip()
        text = text[: m.start()] + f"<target{attrs}>{flat_to_file_xml(value)}</target>" + text[m.end() :]
    if not_found:
        raise ValueError(f"Could not find the target of {', '.join(not_found)} in {target_file}")
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(text)


register_profile(_EXTENSIONS, XLIFF_PROFILE)
register_file_check(_EXTENSIONS, check_file)
register_fix_writer(_EXTENSIONS, write_fixes)
