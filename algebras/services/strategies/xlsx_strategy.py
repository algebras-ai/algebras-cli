"""
Translation strategy for XLSX files.
"""

from typing import Dict, Any, Optional, Callable

from algebras.services.strategies.flat_dict_strategy import FlatDictTranslationStrategy


class XlsxTranslationStrategy(FlatDictTranslationStrategy):
    """
    Strategy for translating XLSX content: the source-language column is translated as a flat dict.

    It is a FlatDictTranslationStrategy, so the Translator passes the file's placeholder profile
    (see Translator._profile_kwarg). A cell whose placeholders were damaged (BatchResult
    failed_indices) is left out of the result: it keeps its old value (or stays empty) and is
    reported, never written damaged.

    Keys cover every translation sheet ("<sheet>!<key>" when there are several). A formatted
    (rich-text) source cell is translated in its tagged form (<runN>…</runN> around each formatted
    run, from read_xlsx_file's "rich_text"), and the result keeps the tags for the writer, which
    gives each span the font of its source run.
    """

    def translate(
        self,
        xlsx_content: Dict[str, Any],
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]] = None,
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]] = None,
        placeholder_profile=None,
    ) -> Dict[str, Any]:
        """
        Translate XLSX content for a specific target language.

        Args:
            xlsx_content: XLSX content dictionary
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation
            on_batch_complete: Optional callback function (not used for XLSX, but kept for interface compatibility)
            placeholder_profile: Placeholder syntaxes to protect (detected from the source column)

        Returns:
            Updated XLSX content with translated strings
        """
        if "translations" not in xlsx_content:
            return xlsx_content

        # Extract source language strings. A formatted (rich-text) cell is sent with its runs as
        # paired <runN> tags (read_xlsx_file's "rich_text"): the tags are markup placeholders, so
        # the model keeps them around the translated spans and the writer gives each span the
        # font of its source run.
        rich_text = xlsx_content.get("rich_text") or {}
        source_strings = {}
        for key, lang_translations in xlsx_content["translations"].items():
            if isinstance(lang_translations, dict) and source_lang in lang_translations:
                tagged = rich_text.get(key, {}).get(source_lang)
                source_strings[key] = tagged if tagged else lang_translations[source_lang]

        translated_strings = super().translate(
            source_strings,
            source_lang,
            target_lang,
            ui_safe,
            glossary_id,
            None,
            translate_text_func,
            placeholder_profile=placeholder_profile,
        )

        rejected = [k for k, v in source_strings.items() if isinstance(v, str) and v.strip() and k not in translated_strings]
        if rejected:
            print(
                f"  ✗ {len(rejected)} cell(s) not translated to {target_lang} (placeholders lost or damaged, "
                f"or the batch failed); they keep their current value: {', '.join(rejected)}"
            )

        # Update the XLSX content (copy each row that changes, so the input is left as it was)
        updated_content = dict(xlsx_content)
        updated_content["translations"] = dict(xlsx_content["translations"])
        # Cells that keep their value are compared with the workbook in their tagged form, so a
        # formatted cell that is not re-translated is not rewritten (and keeps its runs).
        for key, by_lang in rich_text.items():
            if key in updated_content["translations"] and target_lang in by_lang:
                row = dict(updated_content["translations"][key])
                row[target_lang] = by_lang[target_lang]
                updated_content["translations"][key] = row
        for key, translated_value in translated_strings.items():
            if key in updated_content["translations"]:
                row = dict(updated_content["translations"][key])
                row[target_lang] = translated_value
                updated_content["translations"][key] = row

        return updated_content
