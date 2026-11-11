"""
Placeholder engine: extract, mask, unmask, verify and repair.

Translation flow: every placeholder is replaced by an opaque token (⟦0⟧, ⟦1⟧ …) before the text is
sent, so the model never sees "%1$s" and cannot translate or transliterate it. It only decides where
each token goes. After translation the tokens are swapped back for the exact original bytes, and the
result is verified against the source.
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from itertools import product
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from algebras.services.placeholders.profiles import GENERIC_PROFILE, PlaceholderProfile
from algebras.services.placeholders.syntaxes import ORDERED_KINDS, Syntax

TOKEN_OPEN = "⟦"
TOKEN_CLOSE = "⟧"

# Tokens as the model may return them: other bracket styles, spaces, non-ASCII digits.
_TOKEN_RE = re.compile(r"(?:⟦|〚|\[\[)\s*(\d+)\s*(?:⟧|〛|\]\])")

# Count-like placeholders that a plural form covering a single count may leave out
# ("Ein Element" instead of "%d Element").
_COUNT_NAMES = {"count", "n", "num", "number", "quantity", "qty"}


def token(index: int) -> str:
    return f"{TOKEN_OPEN}{index}{TOKEN_CLOSE}"


@dataclass(frozen=True)
class Placeholder:
    raw: str
    syntax: str
    kind: str
    start: int
    end: int

    @property
    def is_positional(self) -> bool:
        if self.kind != "printf":
            return True
        return bool(re.match(r"%\d+\$", self.raw))

    @property
    def is_argument(self) -> bool:
        """False for printf literals: %% and %n."""
        return not (self.kind == "printf" and self.raw in ("%%", "%n"))


@dataclass(frozen=True)
class Problem:
    code: str  # missing | extra | count_mismatch | corrupted | reordered | tags_unbalanced
    placeholder: str
    message: str


class PlaceholderError(Exception):
    def __init__(self, problems: Sequence[Problem]):
        self.problems = list(problems)
        super().__init__("; ".join(p.message for p in self.problems))


@dataclass
class Masked:
    source: str
    text: str
    placeholders: List[Placeholder] = field(default_factory=list)

    @property
    def has_tokens(self) -> bool:
        return bool(self.placeholders)


def _damaged(target: str, strict: Sequence[Placeholder], source: Sequence[Placeholder], profile: PlaceholderProfile) -> List[Placeholder]:
    """
    Lenient matches in `target` that are not valid placeholders. Only syntaxes the source actually
    uses are considered, so "50%больше" in a text without printf placeholders is not flagged.
    """
    source_syntaxes = {p.syntax for p in source}
    syntaxes = [s for s in profile.syntaxes if s.name in source_syntaxes]
    source_raws = {p.raw for p in source}
    spans = [(p.start, p.end) for p in strict]
    return [
        c
        for c in _find(target, syntaxes, lenient=True)
        if c.raw not in source_raws and not any(s <= c.start and c.end <= e for s, e in spans)
    ]


def _find(text: str, syntaxes: Iterable[Syntax], lenient: bool = False) -> List[Placeholder]:
    candidates: List[Placeholder] = []
    for syntax in syntaxes:
        pattern = syntax.lenient if lenient else syntax.pattern
        if pattern is None:
            continue
        for m in pattern.finditer(text):
            if m.end() > m.start():
                candidates.append(Placeholder(m.group(0), syntax.name, syntax.kind, m.start(), m.end()))

    # Leftmost first, then longest: "%1$s" wins over "%1", "{{name}}" over "{name}".
    candidates.sort(key=lambda p: (p.start, -(p.end - p.start)))
    chosen: List[Placeholder] = []
    last_end = -1
    for p in candidates:
        if p.start >= last_end:
            chosen.append(p)
            last_end = p.end
    return chosen


def extract(text: str, profile: PlaceholderProfile = GENERIC_PROFILE) -> List[Placeholder]:
    """All placeholders in `text`, left to right, without overlaps."""
    if not isinstance(text, str) or not text:
        return []
    return [p for p in _find(text, profile.syntaxes) if p.raw not in profile.literal_values]


def mask(text: str, profile: PlaceholderProfile = GENERIC_PROFILE) -> Masked:
    placeholders = extract(text, profile)
    if not placeholders:
        return Masked(source=text, text=text)
    parts: List[str] = []
    pos = 0
    for i, p in enumerate(placeholders):
        parts.append(text[pos : p.start])
        parts.append(token(i))
        pos = p.end
    parts.append(text[pos:])
    return Masked(source=text, text="".join(parts), placeholders=placeholders)


def unmask(
    translated: str,
    masked: Masked,
    profile: PlaceholderProfile = GENERIC_PROFILE,
    drop_allowed: FrozenSet[str] = frozenset(),
) -> str:
    """Put the original placeholders back. Raises PlaceholderError if tokens were lost or changed."""
    if not masked.has_tokens:
        problems = [p for p in verify(masked.source, translated, profile) if p.code != "reordered"]
        if problems:
            raise PlaceholderError(problems)
        return translated

    problems: List[Problem] = []
    seen: Counter = Counter()

    def _restore(m: "re.Match[str]") -> str:
        index = int(m.group(1))  # int() accepts any Unicode decimal digits
        if index >= len(masked.placeholders):
            problems.append(Problem("extra", m.group(0), f"Unknown placeholder token {m.group(0)}"))
            return m.group(0)
        seen[index] += 1
        return masked.placeholders[index].raw

    restored = _TOKEN_RE.sub(_restore, translated)

    for i, p in enumerate(masked.placeholders):
        if seen[i] == 0 and p.raw not in drop_allowed:
            problems.append(Problem("missing", p.raw, f"Placeholder {p.raw} was lost in translation"))
        elif seen[i] > 1:
            problems.append(
                Problem("count_mismatch", p.raw, f"Placeholder {p.raw} appears {seen[i]} times, expected 1")
            )

    if not problems:
        # Catch placeholders the model wrote itself, or corrupted copies of them.
        problems = verify(masked.source, restored, profile, drop_allowed)
    if problems:
        raise PlaceholderError(problems)
    return restored


def verify(
    source: str,
    target: str,
    profile: PlaceholderProfile = GENERIC_PROFILE,
    drop_allowed: FrozenSet[str] = frozenset(),
) -> List[Problem]:
    """Placeholder problems in `target` compared with `source`. Empty list = OK."""
    if not isinstance(target, str) or not target.strip():
        return []
    src = extract(source, profile)
    tgt = extract(target, profile)
    src_count = Counter(p.raw for p in src)
    tgt_count = Counter(p.raw for p in tgt)
    problems: List[Problem] = []

    for raw, n in src_count.items():
        m = tgt_count.get(raw, 0)
        if m == 0:
            if raw not in drop_allowed:
                problems.append(Problem("missing", raw, f"Missing placeholder {raw}"))
        elif m != n and not (m < n and raw in drop_allowed):
            problems.append(
                Problem("count_mismatch", raw, f"Placeholder {raw} appears {m} time(s), source has {n}")
            )
    for raw in tgt_count:
        if raw not in src_count:
            problems.append(Problem("extra", raw, f"Placeholder {raw} is not in the source"))

    for c in _damaged(target, tgt, src, profile):
        problems.append(Problem("corrupted", c.raw, f"Damaged placeholder {c.raw}"))

    if not any(p.code in ("missing", "extra", "count_mismatch") for p in problems):
        src_seq = [p.raw for p in src if p.kind in ORDERED_KINDS and p.is_argument and not p.is_positional]
        tgt_seq = [p.raw for p in tgt if p.kind in ORDERED_KINDS and p.is_argument and not p.is_positional]
        if src_seq != tgt_seq and Counter(src_seq) == Counter(tgt_seq):
            problems.append(
                Problem(
                    "reordered",
                    " ".join(tgt_seq),
                    "Non-positional placeholders changed order "
                    f"({' '.join(src_seq)} → {' '.join(tgt_seq)}); use positional ones like %1$s to reorder",
                )
            )

    if _tags_balanced(src) and not _tags_balanced(tgt):
        problems.append(Problem("tags_unbalanced", "", "Markup tags are not properly opened/closed"))

    return problems


_TAG_NAME = re.compile(r"</?\s*([A-Za-z][A-Za-z0-9_.:-]*)")


def _tags_balanced(placeholders: Sequence[Placeholder]) -> bool:
    stack: List[str] = []
    for p in placeholders:
        if p.kind != "tag" or p.raw.endswith("/>"):
            continue
        m = _TAG_NAME.match(p.raw)
        if not m:
            continue
        name = m.group(1).lower()
        if p.raw.startswith("</"):
            if not stack or stack[-1] != name:
                return False
            stack.pop()
        elif name not in _VOID_TAGS:
            stack.append(name)
    return not stack


_VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "wbr", "area", "base", "col", "source"}


def count_drop_allowed(text: str, profile: PlaceholderProfile = GENERIC_PROFILE) -> FrozenSet[str]:
    """Count-like placeholders in `text` (e.g. %d, %1$d, {count}) that a single-count plural form may omit."""
    allowed = set()
    for p in extract(text, profile):
        if p.kind == "printf" and p.is_argument and re.search(r"(?:hh|h|ll|l|q|L|z|t|j)?[diuU]$", p.raw):
            allowed.add(p.raw)
        elif p.kind == "named":
            name = re.sub(r"[^A-Za-z0-9_]", "", p.raw.split(",")[0]).lower()
            if name in _COUNT_NAMES:
                allowed.add(p.raw)
    return frozenset(allowed)


# ---------------------------------------------------------------------------
# Context for the model
# ---------------------------------------------------------------------------


def placeholder_context(masked: Masked, drop_allowed: FrozenSet[str] = frozenset()) -> Optional[str]:
    """One sentence listing this text's own tokens, or None when it has none."""
    if not masked.has_tokens:
        return None
    tokens = [token(i) for i in range(len(masked.placeholders))]
    listed = ", ".join(tokens)
    noun = "token" if len(tokens) == 1 else "tokens"
    sentence = (
        f"This text contains the placeholder {noun} {listed}. Keep each one exactly once and unchanged: "
        "do not translate, transliterate or add spaces inside them. Move them only if the target "
        "word order requires it."
    )
    optional = [token(i) for i, p in enumerate(masked.placeholders) if p.raw in drop_allowed]
    if optional:
        sentence += (
            f" {', '.join(optional)} may be left out only if the text names its single count in words."
        )
    return sentence


def rewrite_context(context: Optional[str], masked: Masked) -> Optional[str]:
    """Replace this text's raw placeholders inside an existing context with its tokens."""
    if not context or not masked.has_tokens:
        return context
    first_token: Dict[str, str] = {}
    for i, p in enumerate(masked.placeholders):
        first_token.setdefault(p.raw, token(i))
    for raw in sorted(first_token, key=len, reverse=True):
        context = context.replace(raw, first_token[raw])
    return context


def combine_context(
    context: Optional[str], masked: Masked, drop_allowed: FrozenSet[str] = frozenset()
) -> Optional[str]:
    base = rewrite_context(context, masked)
    extra = placeholder_context(masked, drop_allowed)
    if base and extra:
        return f"{base} {extra}"
    return base or extra


# ---------------------------------------------------------------------------
# Repair (deterministic autofix)
# ---------------------------------------------------------------------------

# Characters a model writes instead of the ASCII ones: transliterations and lookalikes
# (Cyrillic, Greek, Uzbek/Kazakh Cyrillic letters). One character may map to several.
_LOOKALIKES: Dict[str, Tuple[str, ...]] = {
    "а": ("a",), "б": ("b",), "в": ("v", "b"), "г": ("g",), "ғ": ("g",), "д": ("d",), "ԁ": ("d",),
    "е": ("e",), "э": ("e",), "ё": ("e",), "ж": ("j",), "з": ("z",), "и": ("i",), "й": ("i",),
    "і": ("i",), "к": ("k",), "қ": ("k", "q"), "л": ("l",), "м": ("m",), "н": ("n",), "о": ("o",),
    "ў": ("o", "u"), "п": ("p",), "р": ("r", "p"), "с": ("s", "c"), "ѕ": ("s",), "т": ("t",),
    "у": ("u", "y"), "ү": ("u",), "ф": ("f",), "х": ("x", "h"), "ҳ": ("h", "x"), "ц": ("c",),
    "ч": ("c",), "ш": ("s",), "ы": ("y",), "ь": ("",), "ъ": ("",), "ю": ("u",), "я": ("a",),
    "α": ("a",), "β": ("b",), "γ": ("g",), "δ": ("d",), "ε": ("e",), "ζ": ("z",), "η": ("h", "n"),
    "ι": ("i",), "κ": ("k",), "λ": ("l",), "μ": ("m",), "ν": ("n", "v"), "ο": ("o",), "π": ("p",),
    "ρ": ("r", "p"), "σ": ("s",), "ς": ("s",), "τ": ("t",), "υ": ("u",), "φ": ("f",), "χ": ("x",),
    "ω": ("o",),
}


def _char_options(ch: str) -> Tuple[str, ...]:
    lower = ch.lower()
    if lower in _LOOKALIKES:
        opts = _LOOKALIKES[lower]
        return tuple(o.upper() for o in opts) + opts if ch != lower else opts
    norm = unicodedata.normalize("NFKC", ch)
    if ch.isdigit():
        return (str(unicodedata.digit(ch)),)
    if norm != ch:
        return (norm,)
    return (ch,)


def _normalizations(raw: str, limit: int = 64) -> List[str]:
    """Possible ASCII readings of a damaged placeholder (spaces removed, lookalikes mapped back)."""
    compact = re.sub(r"\s+", "", raw)
    options = [_char_options(ch) for ch in compact]
    results: List[str] = []
    for combo in product(*options):
        results.append("".join(combo))
        if len(results) >= limit:
            break
    return results


def repair(
    source: str,
    target: str,
    profile: PlaceholderProfile = GENERIC_PROFILE,
    drop_allowed: FrozenSet[str] = frozenset(),
) -> Optional[str]:
    """
    Deterministically fix damaged placeholders in `target`, without calling the translation API.

    1. Damaged or unknown placeholders whose lookalike-normalized form is a missing source
       placeholder are replaced by it (%1$с → %1$s, ％d → %d, {{ имя }} stays unresolved).
    2. If exactly one source placeholder is still missing and exactly one damaged/unknown
       candidate is left, the candidate is replaced (unique slot).

    Returns the fixed text, or None when the target cannot be fixed this way (or needs no fix).
    """
    problems = verify(source, target, profile, drop_allowed)
    if not any(p.code in ("missing", "extra", "corrupted", "count_mismatch") for p in problems):
        return None

    src = extract(source, profile)
    src_count = Counter(p.raw for p in src)
    strict = extract(target, profile)
    missing = src_count - Counter(p.raw for p in strict if p.raw in src_count)

    candidates = [p for p in strict if p.raw not in src_count] + _damaged(target, strict, src, profile)
    candidates.sort(key=lambda p: p.start)

    replacements: List[Tuple[Placeholder, str]] = []
    unresolved: List[Placeholder] = []
    for c in candidates:
        fixed = next((n for n in _normalizations(c.raw) if missing.get(n, 0) > 0), None)
        if fixed is None:
            unresolved.append(c)
            continue
        missing[fixed] -= 1
        replacements.append((c, fixed))

    remaining = [raw for raw, n in missing.items() for _ in range(n)]
    if len(remaining) == 1 and len(unresolved) == 1:
        replacements.append((unresolved[0], remaining[0]))
        unresolved = []

    if not replacements:
        return None

    fixed_text = target
    for c, raw in sorted(replacements, key=lambda r: r[0].start, reverse=True):
        fixed_text = fixed_text[: c.start] + raw + fixed_text[c.end :]

    leftover = [
        p for p in verify(source, fixed_text, profile, drop_allowed) if p.code in ("missing", "extra", "corrupted", "count_mismatch")
    ]
    if leftover:
        return None
    return fixed_text
