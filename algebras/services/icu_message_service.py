"""
ICU message helpers for translation-safe handling.

MVP scope:
- Detect ICU messages that use plural/select/selectordinal.
- Extract only literal text segments for translation.
- Rebuild message from translated segments.
- Validate rebuilt ICU syntax.

Plural branches for the target language: when `prepare` gets the target language, every
`plural` (not `selectordinal` or `select`) gets the CLDR categories the target needs but the
message lacks (en one/other -> ru one/few/many/other). Each new branch starts as a copy of the
source `other` branch, which already holds `#` / `{count}`, so the model translates it with the
grammar of that category. Explicit `=N` branches and the source's own branches stay; branches the
target does not use (an English `one` for Japanese) are kept too, since removing them would
change which text the app shows. Nested plurals are all expanded the same way, inner ones first,
so a copied `other` already carries the expanded inner plural. Every literal segment inside a
CLDR plural branch gets a translator note naming the category and the counts it covers.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pyicumessageformat import Parser


TARGETED_ICU_TYPES = {"plural", "select", "selectordinal"}
ORDINAL_SUFFIX_LITERALS = {"st", "nd", "rd", "th"}

_BRACES = re.compile(r"\{[^{}']*\}|[{}]+")


def _quote_literal(text: str, closes_option: bool = False) -> str:
    """
    Literal text back into ICU syntax. The parser unquotes "'{'" to "{", so literal braces must be
    quoted again or they would turn into arguments ("'{name}'" stays text, not {name}).
    """
    if "{" not in text and "}" not in text and not text.endswith("'"):
        return text
    trailing_apostrophe = closes_option and text.endswith("'")
    # An apostrophe right before a quoted brace would merge with the quote: double it first.
    text = re.sub(r"'(?=[{}])", "''", text)
    text = _BRACES.sub(lambda m: f"'{m.group(0)}'", text)
    if trailing_apostrophe:
        text += "'"
    return text


@dataclass
class LiteralSegment:
    path: Tuple[Any, ...]
    original_text: str
    core_text: str
    leading_ws: str
    trailing_ws: str
    target_type: str
    skip_translation: bool = False
    note: Optional[str] = None


@dataclass
class PreparedMessage:
    original_text: str
    ast: Any
    has_target_icu: bool
    literal_paths: List[Tuple[Any, ...]]
    translatable_segments: List[str]
    literal_segments: List[LiteralSegment]
    # Translator note per translatable segment (plural category and counts), aligned with
    # translatable_segments; empty when no target language was given.
    segment_notes: List[Optional[str]] = field(default_factory=list)


@dataclass
class BatchMapEntry:
    kind: str  # "plain" | "icu"
    original_text: Any
    start: int
    count: int
    prepared: PreparedMessage | None = None

    def note(self, offset: int) -> Optional[str]:
        """Translator note of the segment at `offset` within this message, if any."""
        notes = self.prepared.segment_notes if self.prepared is not None else []
        return notes[offset] if offset < len(notes) else None


class ICUMessageService:
    """Parser-backed ICU helper service."""

    def __init__(self) -> None:
        self._parser = Parser()

    def is_icu(self, text: str) -> bool:
        """True only for target ICU message types."""
        if not isinstance(text, str) or "{" not in text or "}" not in text:
            return False
        try:
            ast = self._parser.parse(text)
        except Exception:
            return False
        return self._contains_target_icu(ast)

    def prepare(
        self, text: str, target_lang: Optional[str] = None, source_lang: Optional[str] = None
    ) -> PreparedMessage:
        """
        Parse and extract literal segments from a targeted ICU message. With `target_lang`, plural
        branches the target language needs are added first (see the module docstring).
        """
        if not isinstance(text, str):
            return PreparedMessage(str(text), [], False, [], [], [])

        try:
            ast = self._parser.parse(text)
        except Exception:
            return PreparedMessage(text, [], False, [], [], [])

        has_target_icu = self._contains_target_icu(ast)
        if not has_target_icu:
            return PreparedMessage(text, ast, False, [], [], [])

        plural_sources: Dict[int, str] = {}
        if target_lang:
            self._expand_plurals(ast, target_lang, plural_sources)

        collected_segments: List[Tuple[Tuple[Any, ...], str]] = []
        self._collect_literal_paths(
            ast,
            tuple(),
            collected_segments,
            in_target_context=False,
            current_target_type="",
        )

        literal_segments: List[LiteralSegment] = []
        for path, target_type in collected_segments:
            original_text = self._get_by_path(ast, path)
            leading_ws = original_text[: len(original_text) - len(original_text.lstrip())]
            trailing_ws = original_text[len(original_text.rstrip()) :]
            core_text = original_text.strip()

            skip_translation = (
                target_type == "selectordinal"
                and core_text in ORDINAL_SUFFIX_LITERALS
                and original_text == core_text
            )

            literal_segments.append(
                LiteralSegment(
                    path=path,
                    original_text=original_text,
                    core_text=core_text,
                    leading_ws=leading_ws,
                    trailing_ws=trailing_ws,
                    target_type=target_type,
                    skip_translation=skip_translation,
                )
            )

        if target_lang:
            for segment in literal_segments:
                segment.note = self._branch_note(
                    ast, segment.path, plural_sources, target_lang, source_lang
                )

        literal_paths = [segment.path for segment in literal_segments]
        translatable_segments = [
            segment.core_text for segment in literal_segments if not segment.skip_translation
        ]
        segment_notes = [
            segment.note for segment in literal_segments if not segment.skip_translation
        ]

        return PreparedMessage(
            original_text=text,
            ast=ast,
            has_target_icu=True,
            literal_paths=literal_paths,
            translatable_segments=translatable_segments,
            literal_segments=literal_segments,
            segment_notes=segment_notes if target_lang else [],
        )

    def rebuild(self, prepared: PreparedMessage, translated_segments: Sequence[str]) -> str:
        """Rebuild ICU message from translated literals."""
        if not prepared.has_target_icu:
            return prepared.original_text

        ast_copy = deepcopy(prepared.ast)
        translated_index = 0
        for segment in prepared.literal_segments:
            if segment.skip_translation:
                replacement_core = segment.core_text
            else:
                replacement_core = (
                    str(translated_segments[translated_index])
                    if translated_index < len(translated_segments)
                    else segment.core_text
                )
                translated_index += 1

            replacement_core = replacement_core.strip()
            if not segment.core_text and not replacement_core:
                # Whitespace-only text between arguments ("# {v}") stays exactly as it was.
                replacement = segment.original_text
            else:
                replacement = f"{segment.leading_ws}{replacement_core}{segment.trailing_ws}"
            self._set_by_path(ast_copy, segment.path, replacement)

        return self._serialize_tokens(ast_copy)

    def validate(self, text: str) -> bool:
        """True if parser accepts the rebuilt ICU text."""
        if not isinstance(text, str):
            return False
        try:
            self._parser.parse(text)
            return True
        except Exception:
            return False

    def preprocess_texts(
        self,
        texts: Sequence[Any],
        target_lang: Optional[str] = None,
        source_lang: Optional[str] = None,
    ) -> Tuple[List[Any], List[BatchMapEntry]]:
        """
        Flatten targeted ICU messages into literal segments.
        With `target_lang`, plurals get the branches that language needs (BatchMapEntry.note
        gives each segment's translator note).
        Returns (flattened_texts, mapping_for_rebuild).
        """
        flattened: List[Any] = []
        mapping: List[BatchMapEntry] = []

        for text in texts:
            if not isinstance(text, str):
                start = len(flattened)
                flattened.append(text)
                mapping.append(
                    BatchMapEntry(kind="plain", original_text=text, start=start, count=1)
                )
                continue

            prepared = self.prepare(text, target_lang, source_lang)
            if not prepared.has_target_icu:
                start = len(flattened)
                flattened.append(text)
                mapping.append(
                    BatchMapEntry(kind="plain", original_text=text, start=start, count=1)
                )
                continue

            start = len(flattened)
            flattened.extend(prepared.translatable_segments)
            mapping.append(
                BatchMapEntry(
                    kind="icu",
                    original_text=text,
                    start=start,
                    count=len(prepared.translatable_segments),
                    prepared=prepared,
                )
            )

        return flattened, mapping

    def postprocess_translations(
        self, mapping: Sequence[BatchMapEntry], translated_flattened: Sequence[Any]
    ) -> List[Any]:
        """Rebuild original list shape after ICU segment translation."""
        rebuilt: List[Any] = []

        for index, entry in enumerate(mapping):
            if entry.kind == "plain":
                if entry.start < len(translated_flattened):
                    rebuilt.append(translated_flattened[entry.start])
                else:
                    rebuilt.append(entry.original_text)
                continue

            if entry.prepared is None:
                rebuilt.append(entry.original_text)
                continue

            segment_slice = translated_flattened[entry.start : entry.start + entry.count]
            rebuilt_text = self.rebuild(entry.prepared, segment_slice)
            if not self.validate(rebuilt_text):
                print(
                    f"  ⚠ ICU validation failed for message at index {index}; keeping raw translated output."
                )
            rebuilt.append(rebuilt_text)

        return rebuilt

    def align_source_branches(self, source: str, target: str) -> str:
        """
        `source` with the plural branches `target` has but the source lacks (ru few/many from an
        en one/other message), each a copy of the source `other` branch. Placeholder checks
        compare the target with this text, so an argument repeated in the new branches is not a
        count mismatch. Returns `source` unchanged when nothing needs adding or either text is not
        a parseable ICU message.
        """
        if not isinstance(source, str) or not isinstance(target, str) or "plural" not in source:
            return source
        try:
            src_ast = self._parser.parse(source)
            tgt_ast = self._parser.parse(target)
        except Exception:
            return source
        src_plurals, tgt_plurals = _plural_nodes(src_ast), _plural_nodes(tgt_ast)
        if not src_plurals or len(src_plurals) != len(tgt_plurals):
            return source
        changed = False
        for s, t in zip(src_plurals, tgt_plurals):
            options = s.get("options")
            target_options = t.get("options")
            if (
                s.get("name") != t.get("name")
                or not isinstance(options, dict)
                or not isinstance(target_options, dict)
                or "other" not in options
            ):
                continue
            # A source branch without the count that the target fills with it (en "one {One
            # item}" -> ru "one {# товар}", since ru one also covers 21, 31 …) was translated
            # from 'other': compare it with 'other'.
            name = s.get("name")
            for key in list(options):
                if (
                    key != "other"
                    and key in target_options
                    and not _mentions_count(options[key], name)
                    and _mentions_count(target_options[key], name)
                    and _mentions_count(options["other"], name)
                ):
                    options[key] = deepcopy(options["other"])
                    changed = True
            added = [key for key in target_options if key not in options]
            if not added:
                continue
            # In the target's branch order, so argument order compares branch by branch.
            merged = {
                key: options[key] if key in options else deepcopy(options["other"])
                for key in target_options
            }
            merged.update({key: value for key, value in options.items() if key not in merged})
            s["options"] = merged
            changed = True
        return self._serialize_tokens(src_ast) if changed else source

    # ------------------------------------------------------------------
    # Plural branches for the target language
    # ------------------------------------------------------------------

    def _expand_plurals(self, ast: Any, target_lang: str, plural_sources: Dict[int, str]) -> None:
        """
        Add the CLDR branches `target_lang` needs to every plural in `ast` (in place).
        `plural_sources` gets the source branches of every plural node (copies included), by id.
        """
        for node in _plural_nodes(ast):
            plural_sources[id(node)] = "; ".join(
                f"{key}: '{self._serialize_tokens(value, in_option=True)}'"
                for key, value in node["options"].items()
            )
        self._expand_node(ast, target_lang, plural_sources)

    def _expand_node(self, node: Any, target_lang: str, plural_sources: Dict[int, str]) -> None:
        if isinstance(node, list):
            for item in node:
                self._expand_node(item, target_lang, plural_sources)
            return
        if not isinstance(node, dict):
            return
        options = node.get("options")
        if not isinstance(options, dict):
            return
        # Inner plurals first: a copied 'other' then already holds the expanded inner plural.
        for option_tokens in options.values():
            self._expand_node(option_tokens, target_lang, plural_sources)
        if node.get("type") != "plural" or "other" not in options:
            return
        _reseed_multi_count_branches(node, target_lang)
        missing = missing_plural_categories(list(options), target_lang)
        if not missing:
            return
        expanded = dict(options)
        for category in missing:
            copy = deepcopy(options["other"])
            for original, copied in zip(_plural_nodes(options["other"]), _plural_nodes(copy)):
                if id(original) in plural_sources:
                    plural_sources[id(copied)] = plural_sources[id(original)]
            expanded[category] = copy
        node["options"] = {key: expanded[key] for key in order_plural_keywords(list(expanded))}

    def _branch_note(
        self,
        ast: Any,
        path: Tuple[Any, ...],
        plural_sources: Dict[int, str],
        target_lang: str,
        source_lang: Optional[str],
    ) -> Optional[str]:
        """Translator note for a literal at `path`: its innermost plural branch, if a CLDR one."""
        from algebras.utils.plural_rules import (
            PLURAL_CATEGORY_ORDER,
            get_category_examples,
            get_language_name,
            get_plural_categories,
        )

        branch = None
        current = ast
        for i, key in enumerate(path):
            if (
                key == "options"
                and isinstance(current, dict)
                and current.get("type") == "plural"
                and i + 1 < len(path)
            ):
                branch = (current, path[i + 1])
            current = current[key]
        if branch is None:
            return None
        node, category = branch
        if category not in PLURAL_CATEGORY_ORDER or id(node) not in plural_sources:
            return None

        target_name = get_language_name(target_lang)
        source_name = get_language_name(source_lang) if source_lang else "Source"
        if category in get_plural_categories(target_lang):
            examples = get_category_examples(target_lang, category)
            usage = ""
            if examples:
                usage = f"It is shown when the count is {examples}"
                usage += "" if examples.endswith("…") else "."
        else:
            usage = f"{target_name} does not use this form; translate it like the general plural."
        parts = [
            f"ICU plural category '{category}' for {target_name}. {usage}".strip(),
            f"{source_name} source branches: {plural_sources[id(node)]}.",
            f"Write the {target_name} text for exactly these counts, using the correct "
            "grammatical form of the counted noun.",
        ]
        return " ".join(parts)

    def _contains_target_icu(self, node: Any) -> bool:
        if isinstance(node, dict):
            node_type = node.get("type")
            if node_type in TARGETED_ICU_TYPES:
                return True
            for value in node.values():
                if self._contains_target_icu(value):
                    return True
            return False
        if isinstance(node, list):
            return any(self._contains_target_icu(item) for item in node)
        return False

    def _collect_literal_paths(
        self,
        node: Any,
        path: Tuple[Any, ...],
        output_paths: List[Tuple[Tuple[Any, ...], str]],
        in_target_context: bool,
        current_target_type: str,
    ) -> None:
        if isinstance(node, str):
            if in_target_context:
                output_paths.append((path, current_target_type))
            return

        if isinstance(node, list):
            for i, item in enumerate(node):
                self._collect_literal_paths(
                    item,
                    path + (i,),
                    output_paths,
                    in_target_context=in_target_context,
                    current_target_type=current_target_type,
                )
            return

        if isinstance(node, dict):
            node_type = node.get("type")
            is_target_node = node_type in TARGETED_ICU_TYPES
            next_target_type = node_type if is_target_node else current_target_type

            for key, value in node.items():
                # Never translate metadata fields.
                if key in {"name", "type", "offset", "hash", "style"}:
                    continue

                # For options, recurse into option payloads only.
                if key == "options" and isinstance(value, dict):
                    for option_key, option_tokens in value.items():
                        self._collect_literal_paths(
                            option_tokens,
                            path + (key, option_key),
                            output_paths,
                            in_target_context=(in_target_context or is_target_node),
                            current_target_type=next_target_type,
                        )
                    continue

                self._collect_literal_paths(
                    value,
                    path + (key,),
                    output_paths,
                    in_target_context=(in_target_context or is_target_node),
                    current_target_type=next_target_type,
                )

    def _get_by_path(self, node: Any, path: Tuple[Any, ...]) -> Any:
        current = node
        for key in path:
            current = current[key]
        return current

    def _set_by_path(self, node: Any, path: Tuple[Any, ...], value: Any) -> None:
        current = node
        for key in path[:-1]:
            current = current[key]
        current[path[-1]] = value

    def _serialize_tokens(self, tokens: Any, in_option: bool = False) -> str:
        if isinstance(tokens, str):
            return _quote_literal(tokens, closes_option=in_option)

        if isinstance(tokens, list):
            parts = []
            for i, token in enumerate(tokens):
                if isinstance(token, str):
                    # A trailing apostrophe before an argument or a closing brace would start
                    # ICU quoting and swallow it ("l'{name}"): double it.
                    followed = i + 1 < len(tokens) or in_option
                    parts.append(_quote_literal(token, closes_option=followed))
                else:
                    parts.append(self._serialize_tokens(token))
            return "".join(parts)

        if isinstance(tokens, dict):
            name = tokens.get("name", "")
            node_type = tokens.get("type")

            if node_type == "number" and tokens.get("hash"):
                return "#"

            if node_type in TARGETED_ICU_TYPES:
                options = tokens.get("options", {})
                option_chunks = []
                for option_key, option_value in options.items():
                    option_chunks.append(
                        f"{option_key} {{{self._serialize_tokens(option_value, in_option=True)}}}"
                    )

                if node_type in {"plural", "selectordinal"} and tokens.get("offset"):
                    options_part = " ".join(
                        [f"offset:{tokens['offset']}"] + option_chunks
                    )
                else:
                    options_part = " ".join(option_chunks)

                return f"{{{name}, {node_type}, {options_part}}}"

            if node_type:
                # pyicumessageformat stores the style ("compact", "yMd") under "format".
                style = tokens.get("style") or tokens.get("format")
                if style:
                    return f"{{{name}, {node_type}, {style}}}"
                return f"{{{name}, {node_type}}}"

            if name:
                return f"{{{name}}}"

        return str(tokens)


def _plural_nodes(node: Any) -> List[Dict[str, Any]]:
    """Plural argument nodes of a parsed message, in pre-order."""
    found: List[Dict[str, Any]] = []
    if isinstance(node, list):
        for item in node:
            found.extend(_plural_nodes(item))
    elif isinstance(node, dict):
        if node.get("type") == "plural":
            found.append(node)
        options = node.get("options")
        if isinstance(options, dict):
            for value in options.values():
                found.extend(_plural_nodes(value))
    return found


def _mentions_count(tokens: Any, name: Optional[str]) -> bool:
    """True if a branch shows the count: '#' or the plural's own argument ({count})."""
    if isinstance(tokens, list):
        return any(_mentions_count(t, name) for t in tokens)
    if isinstance(tokens, dict):
        if tokens.get("hash") or (name and tokens.get("name") == name):
            return True
        options = tokens.get("options")
        if isinstance(options, dict):
            return any(_mentions_count(v, name) for v in options.values())
    return False


def _reseed_multi_count_branches(node: Dict[str, Any], target_lang: str) -> None:
    """
    A source branch without the count ("one {One item}") becomes a copy of 'other' when the
    target's category covers several counts (ru one: 1, 21, 31 …): translated as written, it
    would say "one" for 21 items.
    """
    from algebras.utils.plural_rules import covers_single_count, get_plural_categories, is_known_language

    if not target_lang or not is_known_language(target_lang):
        return
    options = node["options"]
    name = node.get("name")
    if not _mentions_count(options["other"], name):
        return
    needed = get_plural_categories(target_lang)
    for key in list(options):
        if (
            key in needed
            and key != "other"
            and not covers_single_count(target_lang, key)
            and not _mentions_count(options[key], name)
        ):
            options[key] = deepcopy(options["other"])


def _explicitly_covered(category: str, keywords: Sequence[str], target_lang: str) -> bool:
    """True if an explicit branch already covers the only count of `category` (=1 for German one)."""
    from algebras.utils.plural_rules import get_category_examples

    examples = get_category_examples(target_lang, category)
    return bool(examples) and examples.isdigit() and f"={examples}" in keywords


def missing_plural_categories(keywords: Sequence[str], target_lang: str) -> List[str]:
    """
    CLDR categories `target_lang` needs that a plural with these branch keywords lacks, in CLDR
    order. A category whose only count has an explicit branch (=1 for German one) is not missing.
    Unknown languages need nothing.
    """
    from algebras.utils.plural_rules import get_plural_categories, is_known_language

    keywords = list(keywords)
    if not target_lang or not is_known_language(target_lang):
        return []
    return [
        c
        for c in get_plural_categories(target_lang)
        if c not in keywords and not _explicitly_covered(c, keywords, target_lang)
    ]


def order_plural_keywords(keywords: Sequence[str]) -> List[str]:
    """Explicit =N branches first (in their order), then CLDR categories, then anything else."""
    from algebras.utils.plural_rules import PLURAL_CATEGORY_ORDER

    keywords = list(keywords)
    explicit = [k for k in keywords if k.startswith("=")]
    cldr = [c for c in PLURAL_CATEGORY_ORDER if c in keywords]
    rest = [k for k in keywords if k not in explicit and k not in cldr]
    return explicit + cldr + rest


_shared_service: Optional[ICUMessageService] = None


def align_source_branches(source: str, target: str) -> str:
    """Module-level ICUMessageService.align_source_branches for placeholder checks."""
    global _shared_service
    if _shared_service is None:
        _shared_service = ICUMessageService()
    return _shared_service.align_source_branches(source, target)
