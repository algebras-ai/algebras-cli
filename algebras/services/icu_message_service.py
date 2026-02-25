"""
ICU message helpers for translation-safe handling.

MVP scope:
- Detect ICU messages that use plural/select/selectordinal.
- Extract only literal text segments for translation.
- Rebuild message from translated segments.
- Validate rebuilt ICU syntax.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, List, Sequence, Tuple

from pyicumessageformat import Parser


TARGETED_ICU_TYPES = {"plural", "select", "selectordinal"}
ORDINAL_SUFFIX_LITERALS = {"st", "nd", "rd", "th"}


@dataclass
class LiteralSegment:
    path: Tuple[Any, ...]
    original_text: str
    core_text: str
    leading_ws: str
    trailing_ws: str
    target_type: str
    skip_translation: bool = False


@dataclass
class PreparedMessage:
    original_text: str
    ast: Any
    has_target_icu: bool
    literal_paths: List[Tuple[Any, ...]]
    translatable_segments: List[str]
    literal_segments: List[LiteralSegment]


@dataclass
class BatchMapEntry:
    kind: str  # "plain" | "icu"
    original_text: Any
    start: int
    count: int
    prepared: PreparedMessage | None = None


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

    def prepare(self, text: str) -> PreparedMessage:
        """Parse and extract literal segments from a targeted ICU message."""
        if not isinstance(text, str):
            return PreparedMessage(str(text), [], False, [], [], [])

        try:
            ast = self._parser.parse(text)
        except Exception:
            return PreparedMessage(text, [], False, [], [], [])

        has_target_icu = self._contains_target_icu(ast)
        if not has_target_icu:
            return PreparedMessage(text, ast, False, [], [], [])

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

        literal_paths = [segment.path for segment in literal_segments]
        translatable_segments = [
            segment.core_text for segment in literal_segments if not segment.skip_translation
        ]

        return PreparedMessage(
            original_text=text,
            ast=ast,
            has_target_icu=True,
            literal_paths=literal_paths,
            translatable_segments=translatable_segments,
            literal_segments=literal_segments,
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

    def preprocess_texts(self, texts: Sequence[Any]) -> Tuple[List[Any], List[BatchMapEntry]]:
        """
        Flatten targeted ICU messages into literal segments.
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

            prepared = self.prepare(text)
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

    def _serialize_tokens(self, tokens: Any) -> str:
        if isinstance(tokens, str):
            return tokens

        if isinstance(tokens, list):
            return "".join(self._serialize_tokens(token) for token in tokens)

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
                        f"{option_key} {{{self._serialize_tokens(option_value)}}}"
                    )

                if node_type in {"plural", "selectordinal"} and tokens.get("offset"):
                    options_part = " ".join(
                        [f"offset:{tokens['offset']}"] + option_chunks
                    )
                else:
                    options_part = " ".join(option_chunks)

                return f"{{{name}, {node_type}, {options_part}}}"

            if node_type:
                style = tokens.get("style")
                if style:
                    return f"{{{name}, {node_type}, {style}}}"
                return f"{{{name}, {node_type}}}"

            if name:
                return f"{{{name}}}"

        return str(tokens)
