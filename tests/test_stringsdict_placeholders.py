"""
.stringsdict placeholder protection: %#@var@ references, printf specifiers in plural forms and the
plural-rule metadata survive translation; damaged files are reported and fixed by
'algebras placeholders'.
"""

import json
import os
import re

import pytest

from algebras.commands import placeholders_command
from algebras.commands.translate_command import (
    _load_file_contents,
    _translate_plural_aware,
    _write_translated_content,
)
from algebras.services.placeholders import extract, profile_for_path
from algebras.services.translator import Translator
from algebras.utils.file_format_handlers import get_handler
from algebras.utils.ios_stringsdict_handler import (
    build_plural_contexts,
    extract_format_specifiers,
    is_reference_only,
    plural_source_text,
    read_ios_stringsdict_file,
    update_translatable_strings,
    validate_plural_forms,
    write_ios_stringsdict_file,
    write_stringsdict_fixes,
)

from tests.test_placeholders_translation import transliterate
from tests.test_stringsdict_plurals import _batch_response, _mock_config, _plural

SOURCE = {
    "files_in_folder": {
        "NSStringLocalizedFormatKey": "%#@fileCount@",
        "fileCount": _plural(
            {"one": "%1$@ has one file", "other": "%1$@ has %ld files"}, value_type="ld"
        ),
    },
    "found_items": {
        "NSStringLocalizedFormatKey": "Found %#@itemCount@",
        "itemCount": _plural({"one": "%d item", "other": "%d items"}),
    },
}


# --- profile / extraction ------------------------------------------------------


def test_variable_reference_is_one_placeholder():
    profile = profile_for_path("en.lproj/Localizable.stringsdict")
    assert profile.name == "ios_stringsdict"
    assert [p.raw for p in extract("%1$#@files@ in %2$#@folders@, %ld", profile)] == [
        "%1$#@files@",
        "%2$#@folders@",
        "%ld",
    ]
    assert extract_format_specifiers("%#@items@ and %ld, 100%%") == ["%#@items@", "%ld"]


def test_reference_only_format_keys():
    assert is_reference_only("%#@items@")
    assert is_reference_only("%1$#@a@ %2$#@b@")
    assert not is_reference_only("Found %#@items@")
    assert not is_reference_only("plain")


def test_multi_count_form_is_sent_with_the_count_placeholder():
    plural = SOURCE["found_items"]["itemCount"]
    assert plural_source_text(plural, "one", "ru") == "%d item"  # already has the count
    assert plural_source_text(SOURCE["files_in_folder"]["fileCount"], "one", "ru") == "%1$@ has %ld files"
    single = _plural({"one": "One item", "other": "%d items"})
    assert plural_source_text(single, "one", "de") == "One item"  # de one = 1 only
    assert plural_source_text(single, "one", "ru") == "%d items"
    assert plural_source_text(single, "few", "ru") == "%d items"


def test_context_no_longer_lists_fixed_placeholder_examples():
    contexts = build_plural_contexts(SOURCE, "en", "ru")
    few = contexts["files_in_folder.fileCount.few"]
    assert "such as %d, %ld" not in few
    # The count rule for multi-count forms stays, naming the integer placeholder (not %1$@).
    assert "number placeholder (%ld)" in few


# --- translation end to end ----------------------------------------------------


@pytest.fixture
def ios_project(tmp_path):
    source = str(tmp_path / "en.lproj" / "Localizable.stringsdict")
    os.makedirs(os.path.dirname(source))
    write_ios_stringsdict_file(source, SOURCE)
    target = str(tmp_path / "ru.lproj" / "Localizable.stringsdict")
    os.makedirs(os.path.dirname(target))
    return source, target


_FORM = re.compile(r"plural form '(\w+)'")


def _fake_api(sent, answer):
    """requests.post stand-in: answer(text, form) -> translation."""

    def post(url, headers=None, json=None, **kwargs):
        sent.append(json)
        contexts = json.get("contexts") or [None] * len(json["texts"])
        out = []
        for text, context in zip(json["texts"], contexts):
            match = _FORM.search(context or "")
            out.append(answer(text, match.group(1) if match else None))
        return _batch_response(out)

    return post


def _translate(source, target, lang, monkeypatch, answer):
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    sent = []
    monkeypatch.setattr("algebras.services.api_client.requests.post", _fake_api(sent, answer))
    config = _mock_config()
    translator = Translator(config=config)
    translator.api_client.set_sync_batch(True)
    handler = get_handler(source, config)
    source_content, target_content, source_raw, target_raw, contexts = _load_file_contents(
        source, target, handler, "en", lang, config
    )
    missing = sorted(set(source_content) - set(target_content))
    translated = _translate_plural_aware(
        translator.translate_missing_keys_batch,
        source_content,
        target_content,
        missing,
        lang,
        source_file_path=source,
        contexts=contexts,
    )
    _write_translated_content(
        target, translated, handler, set(missing), False,
        source_file=source, source_language="en", target_language=lang,
        source_raw_content=source_raw, target_raw_content=target_raw,
    )
    return sent


def test_transliterating_model_keeps_every_placeholder(ios_project, monkeypatch):
    source, target = ios_project
    sent = _translate(source, target, "ru", monkeypatch, lambda text, form: transliterate(f"[{form}] {text}"))

    written = read_ios_stringsdict_file(target)
    files = written["files_in_folder"]
    assert files["NSStringLocalizedFormatKey"] == "%#@fileCount@"
    assert files["fileCount"]["NSStringFormatValueTypeKey"] == "ld"
    for form in ("one", "few", "many", "other"):
        assert "%1$@" in files["fileCount"][form] and "%ld" in files["fileCount"][form], form
    items = written["found_items"]
    assert items["NSStringLocalizedFormatKey"] == "Found %#@itemCount@"
    for form in ("one", "few", "many", "other"):
        assert items["itemCount"][form].count("%d") == 1, form

    # Variable names, format keys and raw specifiers never reach the API.
    texts = [t for body in sent for t in body["texts"]]
    assert texts and not any("%" in t or "fileCount" in t or "itemCount" in t for t in texts)
    assert validate_plural_forms(written, SOURCE, "ru") == []


def _drop_tokens_for(forms):
    def answer(text, form):
        if form in forms:
            return re.sub(r"⟦\d+⟧\s*", "", text) or "x"
        return f"T {text}"

    return answer


def test_single_count_form_may_drop_the_count(tmp_path, monkeypatch):
    source = str(tmp_path / "en.lproj" / "Localizable.stringsdict")
    os.makedirs(os.path.dirname(source))
    write_ios_stringsdict_file(source, {"found_items": SOURCE["found_items"]})
    target = str(tmp_path / "de.lproj" / "Localizable.stringsdict")
    os.makedirs(os.path.dirname(target))

    _translate(source, target, "de", monkeypatch, lambda text, form: "Ein Element" if form == "one" else f"T {text}")

    plural = read_ios_stringsdict_file(target)["found_items"]["itemCount"]
    assert plural["one"] == "Ein Element"
    assert plural["other"] == "T %d items"


def test_multi_count_form_without_count_is_rejected_not_written(ios_project, monkeypatch):
    source, target = ios_project
    _translate(source, target, "ru", monkeypatch, _drop_tokens_for({"few"}))

    written = read_ios_stringsdict_file(target)
    for entry, var in (("files_in_folder", "fileCount"), ("found_items", "itemCount")):
        plural = written[entry][var]
        assert "few" not in plural  # neither "" nor the English text
        assert {"one", "many", "other"} <= set(plural)
    warnings = validate_plural_forms(written, SOURCE, "ru")
    assert "found_items.itemCount: missing plural forms few" in warnings


def test_rejected_other_leaves_new_entry_out(ios_project, monkeypatch):
    source, target = ios_project
    _translate(source, target, "ru", monkeypatch, _drop_tokens_for({"other"}))

    written = read_ios_stringsdict_file(target)
    # No English 'other' written; without 'other' the plural rule would be broken, so the
    # entries stay missing and the next run retries them.
    assert "files_in_folder" not in written and "found_items" not in written


def test_update_copies_type_keys_and_reference_only_format_key_from_source():
    target = {
        "files_in_folder": {
            "NSStringLocalizedFormatKey": "%#@файлы@",
            "fileCount": _plural({"one": "%1$@: %ld файл", "other": "%1$@: %ld файлов"}, value_type="д"),
        }
    }
    updated = update_translatable_strings(target, {}, {"files_in_folder": SOURCE["files_in_folder"]})
    entry = updated["files_in_folder"]
    assert entry["NSStringLocalizedFormatKey"] == "%#@fileCount@"
    assert entry["fileCount"]["NSStringFormatValueTypeKey"] == "ld"
    assert entry["fileCount"]["one"] == "%1$@: %ld файл"


# --- check + fix ---------------------------------------------------------------

SOURCE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>files_in_folder</key>
\t<dict>
\t\t<key>NSStringLocalizedFormatKey</key>
\t\t<string>%#@fileCount@</string>
\t\t<key>fileCount</key>
\t\t<dict>
\t\t\t<key>NSStringFormatSpecTypeKey</key>
\t\t\t<string>NSStringPluralRuleType</string>
\t\t\t<key>NSStringFormatValueTypeKey</key>
\t\t\t<string>ld</string>
\t\t\t<key>one</key>
\t\t\t<string>%1$@ has %ld file</string>
\t\t\t<key>other</key>
\t\t\t<string>%1$@ has %ld files</string>
\t\t</dict>
\t</dict>
</dict>
</plist>
"""

# Keys deliberately not sorted (other before one): the fix must keep the order.
TARGET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>files_in_folder</key>
\t<dict>
\t\t<key>NSStringLocalizedFormatKey</key>
\t\t<string>%#@файлы@</string>
\t\t<key>fileCount</key>
\t\t<dict>
\t\t\t<key>NSStringFormatSpecTypeKey</key>
\t\t\t<string>NSStringPluralRuleType</string>
\t\t\t<key>NSStringFormatValueTypeKey</key>
\t\t\t<string>д</string>
\t\t\t<key>other</key>
\t\t\t<string>В %1$@ %ld файла</string>
\t\t\t<key>one</key>
\t\t\t<string>В %1$@ %ld файл &amp; всё</string>
\t\t\t<key>few</key>
\t\t\t<string>В %1$@ %д файла</string>
\t\t</dict>
\t</dict>
</dict>
</plist>
"""


@pytest.fixture
def check_project(tmp_path, monkeypatch):
    (tmp_path / "en.lproj").mkdir()
    (tmp_path / "ru.lproj").mkdir()
    (tmp_path / "en.lproj" / "Localizable.stringsdict").write_text(SOURCE_XML, encoding="utf-8")
    (tmp_path / "ru.lproj" / "Localizable.stringsdict").write_text(TARGET_XML, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "ru"],
                "source_files": {
                    "en.lproj/Localizable.stringsdict": {
                        "destination_path": "%algebras_locale_code%.lproj/Localizable.stringsdict"
                    }
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _report(capsys):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json")
    return code, json.loads(capsys.readouterr().out)


def test_check_reports_variable_name_specifier_type_key_and_missing_form(check_project, capsys):
    code, report = _report(capsys)
    assert code == 1
    issues = {i["key"]: i for i in report["issues"]}
    assert set(issues) == {
        "files_in_folder.NSStringLocalizedFormatKey",
        "files_in_folder.fileCount.NSStringFormatValueTypeKey",
        "files_in_folder.fileCount.few",
        "files_in_folder.fileCount.many",
    }
    fmt = issues["files_in_folder.NSStringLocalizedFormatKey"]
    assert {p["code"] for p in fmt["problems"]} == {"missing", "corrupted"}
    assert fmt["fixed"] == "%#@fileCount@"
    assert issues["files_in_folder.fileCount.NSStringFormatValueTypeKey"]["fixed"] == "ld"
    few = issues["files_in_folder.fileCount.few"]
    assert {p["code"] for p in few["problems"]} == {"missing", "corrupted"}
    assert few["fixed"] == "В %1$@ %ld файла"
    many = issues["files_in_folder.fileCount.many"]
    assert many["problems"][0]["code"] == "missing_form"
    assert many["problems"][0]["message"] == "files_in_folder.fileCount: missing plural forms many"
    assert many["fixed"] is None


def test_fix_repairs_in_place_and_is_idempotent(check_project, capsys):
    target = check_project / "ru.lproj" / "Localizable.stringsdict"
    assert placeholders_command.execute(fix=True, output_format="json") == 2  # 'many' needs translation

    fixed = target.read_text(encoding="utf-8")
    expected = (
        TARGET_XML.replace("%#@файлы@", "%#@fileCount@")
        .replace("<string>д</string>", "<string>ld</string>")
        .replace("%д файла", "%ld файла")
    )
    assert fixed == expected  # only the fixed values changed; order, escaping, formatting kept

    code, report = _report(capsys)
    assert [i["key"] for i in report["issues"]] == ["files_in_folder.fileCount.many"]

    placeholders_command.execute(fix=True, output_format="json")
    assert target.read_text(encoding="utf-8") == expected


def test_dry_run_writes_nothing(check_project):
    target = check_project / "ru.lproj" / "Localizable.stringsdict"
    assert placeholders_command.execute(fix=True, dry_run=True, output_format="json") == 1
    assert target.read_text(encoding="utf-8") == TARGET_XML


def test_fix_writer_handles_escaping_and_empty_strings(tmp_path):
    path = tmp_path / "x.stringsdict"
    path.write_text(
        '<?xml version="1.0"?>\n<plist version="1.0">\n<dict>\n'
        "<key>a.b</key><dict><key>NSStringLocalizedFormatKey</key><string/>"
        "<key>v</key><dict><key>NSStringFormatSpecTypeKey</key><string>NSStringPluralRuleType</string>"
        "<key>other</key><string>x</string></dict></dict>\n"
        "<key>list</key><array><string>keep</string></array>\n</dict>\n</plist>\n",
        encoding="utf-8",
    )
    not_found = write_stringsdict_fixes(
        str(path), {"a.b.NSStringLocalizedFormatKey": "%#@v@", "a.b.v.other": "<%d> & more", "nope": "z"}
    )
    assert not_found == ["nope"]
    content = read_ios_stringsdict_file(str(path))
    assert content["a.b"]["NSStringLocalizedFormatKey"] == "%#@v@"
    assert content["a.b"]["v"]["other"] == "<%d> & more"
    assert "&lt;%d&gt; &amp; more" in path.read_text(encoding="utf-8")
