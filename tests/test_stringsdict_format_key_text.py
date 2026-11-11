"""
.stringsdict NSStringLocalizedFormatKey with text around its references ("Found %#@items@ in
%#@folders@"): the text is translated, the references are kept (masked as tokens), the key is
counted by 'status', and a reference-only key ("%#@items@") is still copied from the source.
"""

import os
import re

import pytest

from algebras.utils.ios_stringsdict_handler import (
    extract_translatable_strings,
    is_translatable_format_key,
    read_ios_stringsdict_file,
    update_translatable_strings,
    write_ios_stringsdict_file,
)
from algebras.utils.lang_validator import validate_language_files

from tests.test_stringsdict_placeholders import _translate
from tests.test_stringsdict_plurals import _plural

FMT = "NSStringLocalizedFormatKey"

SOURCE = {
    "found": {
        FMT: "Found %#@items@ in %#@folders@",
        "items": _plural({"one": "%d item", "other": "%d items"}),
        "folders": _plural({"one": "%d folder", "other": "%d folders"}),
    },
    "count_only": {
        FMT: "%#@count@",
        "count": _plural({"one": "One file", "other": "%d files"}),
    },
}


@pytest.fixture
def project(tmp_path):
    source = str(tmp_path / "en.lproj" / "Localizable.stringsdict")
    os.makedirs(os.path.dirname(source))
    write_ios_stringsdict_file(source, SOURCE)
    target = str(tmp_path / "de.lproj" / "Localizable.stringsdict")
    os.makedirs(os.path.dirname(target))
    return source, target


def _german(text, form):
    return text.replace("Found", "Gefunden:")


def test_format_key_with_text_is_extracted_reference_only_is_not():
    flat = extract_translatable_strings(SOURCE)
    assert flat["found." + FMT] == "Found %#@items@ in %#@folders@"
    assert "count_only." + FMT not in flat
    assert not is_translatable_format_key(FMT, "%1$#@a@ %2$#@b@")
    assert not is_translatable_format_key(FMT, "%#@Auth.eula_count@")


def test_format_key_text_is_translated_and_references_kept(project, monkeypatch):
    source, target = project
    sent = _translate(source, target, "de", monkeypatch, _german)

    written = read_ios_stringsdict_file(target)
    assert written["found"][FMT] == "Gefunden: %#@items@ in %#@folders@"
    assert written["count_only"][FMT] == "%#@count@"  # copied, as before
    # The model saw tokens, never the variable names.
    texts = [t for body in sent for t in body["texts"]]
    fmt_texts = [t for t in texts if t.startswith("Found")]
    assert fmt_texts and not any("%#@" in t or "items@" in t for t in fmt_texts)
    assert all(re.search(r"⟦\d+⟧", t) for t in fmt_texts)

    # 'status' / missing-key detection counts the format key, and it is translated now.
    _valid, missing = validate_language_files(source, target, "en", "de")
    assert not missing


def test_untranslated_format_key_is_reported_missing(project):
    source, target = project
    flat = extract_translatable_strings(SOURCE)
    translations = {k: f"DE {v}" for k, v in flat.items() if not k.endswith(FMT)}
    write_ios_stringsdict_file(target, update_translatable_strings({}, translations, SOURCE))
    written = read_ios_stringsdict_file(target)
    # Not written in English: the entry is left out so 'status' reports it and it is retried.
    assert "found" not in written
    _valid, missing = validate_language_files(source, target, "en", "de")
    assert "found." + FMT in missing


def test_format_key_that_lost_a_reference_is_not_written():
    target = {
        "found": {
            FMT: "Gefunden: %#@items@ in %#@folders@",
            "items": _plural({"one": "%d Element", "other": "%d Elemente"}),
            "folders": _plural({"one": "%d Ordner", "other": "%d Ordner"}),
        }
    }
    updated = update_translatable_strings(target, {"found." + FMT: "Gefunden: %#@items@"}, SOURCE)
    assert updated["found"][FMT] == "Gefunden: %#@items@ in %#@folders@"
