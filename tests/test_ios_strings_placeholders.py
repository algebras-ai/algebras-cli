"""
iOS .strings placeholder safety: profile, escaping round-trip, verify strictness, end-to-end
translation with a transliterating model, and 'algebras placeholders' check / --fix in place.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, translate_command
from algebras.services.batch_processor import BatchProcessor
from algebras.services.placeholders import extract, mask, profile_for_path, repair, verify
from algebras.services.placeholders.fix_writers import get_fix_writer
from algebras.services.placeholders.formats.ios_strings import IOS_STRINGS_PROFILE
from algebras.utils.ios_strings_handler import (
    _escape_ios_string,
    _unescape_ios_string,
    read_ios_strings_file,
    update_ios_strings_file_in_place,
    write_ios_strings_file,
)

P = IOS_STRINGS_PROFILE

SOURCE_STRINGS = r"""/* Greeting shown on the home screen */
"welcome_user" = "Welcome, %@!";

// Two arguments; positional, so translations may reorder them
"files_shared" = "%1$@ shared %2$d files";
"total_price" = "Total: %.2f";
"discount" = "Save 20%% today";
"quote" = "Tap \"Continue\" to go on\nNext line";
"link" = "Read the <a href=\"%@\">terms</a>";
"items_count" = "%ld items";
"sent_by" = "%@ sent %d photos";
"plain" = "Hello";
"""

_LATIN_TO_CYRILLIC = str.maketrans(dict(zip("sdcfSDabeiklmnoprtuvxyz", "сдсфСДабеиклмнопртувхйз")))


def transliterate(text: str) -> str:
    """What the model did for uz-Cyrl: every Latin letter becomes Cyrillic."""
    return text.translate(_LATIN_TO_CYRILLIC)


@pytest.fixture(autouse=True)
def default_normalization():
    # _escape_ios_string reads the project config; keep tests independent of the cwd.
    cfg = MagicMock()
    cfg.exists.return_value = False
    with patch("algebras.utils.ios_strings_handler.Config", return_value=cfg):
        yield


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_profile_is_registered_for_strings_only():
    assert profile_for_path("App/en.lproj/Localizable.strings").name == "ios_strings"
    assert profile_for_path("App/en.lproj/Localizable.STRINGS").name == "ios_strings"
    assert profile_for_path("App/en.lproj/Localizable.stringsdict").name != "ios_strings"
    assert get_fix_writer("App/uz.lproj/Localizable.strings") is not None


def test_objc_specifiers_and_tags_are_extracted():
    text = 'Hi %@, %1$@ %2$d %3$ld %lld %lu %.2f %% <a href="%@">x</a>'
    raws = [p.raw for p in extract(text, P)]
    assert raws == ["%@", "%1$@", "%2$d", "%3$ld", "%lld", "%lu", "%.2f", "%%", '<a href="%@">', "</a>"]


def test_link_tag_with_specifier_is_one_token():
    masked = mask('Read the <a href="%@">terms</a>', P)
    assert masked.text == "Read the ⟦0⟧terms⟦1⟧"


# ---------------------------------------------------------------------------
# Escaping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "%1$@ shared %2$d files",
        "Save 20%% today, %.2f",
        'Tap "Continue"\nNext\tline',
        'Path C:\\new and \\"quoted\\"',
        'Read <a href="%@">terms</a>',
    ],
)
def test_escape_round_trip_keeps_placeholders(value):
    escaped = _escape_ios_string(value)
    assert _unescape_ios_string(escaped) == value
    printf = [p.raw for p in extract(value, P) if p.kind == "printf"]
    assert [p.raw for p in extract(escaped, P) if p.kind == "printf"] == printf


def test_escaped_backslash_before_n_is_not_a_newline():
    assert _unescape_ios_string(r"C:\\new") == "C:\\new"
    assert _unescape_ios_string(r"line\nnext") == "line\nnext"
    assert _unescape_ios_string(r"\U2026") == "…"


def test_file_round_trip(tmp_path):
    path = tmp_path / "Localizable.strings"
    path.write_text(SOURCE_STRINGS, encoding="utf-8")
    data = read_ios_strings_file(str(path))
    assert data["files_shared"] == "%1$@ shared %2$d files"
    assert data["discount"] == "Save 20%% today"
    assert data["quote"] == 'Tap "Continue" to go on\nNext line'
    assert data["link"] == 'Read the <a href="%@">terms</a>'

    out = tmp_path / "out.strings"
    write_ios_strings_file(str(out), data)
    assert read_ios_strings_file(str(out)) == data


def test_commented_out_entries_are_ignored(tmp_path):
    path = tmp_path / "Localizable.strings"
    path.write_text(
        '"a" = "new %@";\n/* "a" = "old"; */\n// "b" = "gone";\n"url" = "http://example.com";\n',
        encoding="utf-8",
    )
    assert read_ios_strings_file(str(path)) == {"a": "new %@", "url": "http://example.com"}


# ---------------------------------------------------------------------------
# Verify: stricter rules for iOS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source,target",
    [("%d items", "%ld элемент"), ("%ld items", "%d элемент"), ("%lld items", "%ld элемент"), ("%lu", "%u")],
)
def test_length_modifier_mismatch_is_an_error(source, target):
    codes = {p.code for p in verify(source, target, P)}
    assert {"missing", "extra"} <= codes
    # Unique slot: the source's specifier is restored.
    assert repair(source, target, P) == target.replace(extract(target, P)[0].raw, extract(source, P)[0].raw)


def test_positional_swap_ok_non_positional_swap_rejected():
    assert verify("%1$@ shared %2$d files", "%2$d та файлни %1$@ улашди", P) == []
    problems = verify("%@ sent %d photos", "%d та расмни %@ юборди", P)
    assert [p.code for p in problems] == ["reordered"]
    assert repair("%@ sent %d photos", "%d та расмни %@ юборди", P) is None


@pytest.mark.parametrize(
    "source,damaged,fixed",
    [
        ("Hi %@!", "Салом ％＠!", "Салом %@!"),
        ("Hi %@!", "Салом %＠!", "Салом %@!"),
        ("Hi %@!", "Салом % @!", "Салом %@!"),
        ("%1$@ shared %2$d", "%1$ @ улашди %2$d", "%1$@ улашди %2$d"),
        ("%1$@ shared %2$d", "%1＄＠ улашди %2$д", "%1$@ улашди %2$d"),
        ("Total: %.2f", "Жами: %.2ф", "Жами: %.2f"),
        ("%ld items", "%lд элемент", "%ld элемент"),
    ],
)
def test_lookalike_repair(source, damaged, fixed):
    assert verify(source, damaged, P)
    assert repair(source, damaged, P) == fixed
    assert verify(source, fixed, P) == []


# ---------------------------------------------------------------------------
# Translation: masking with a transliterating model
# ---------------------------------------------------------------------------


def _swap_two_tokens(text: str) -> str:
    # Only "⟦0⟧ … ⟦1⟧" texts (two arguments), not a "…⟦0⟧terms⟦1⟧" open/close tag pair.
    if text.startswith("⟦0⟧") and "⟦1⟧" in text and "⟦2⟧" not in text:
        return text.replace("⟦0⟧", "\0").replace("⟦1⟧", "⟦0⟧").replace("\0", "⟦1⟧")
    return text


def test_batch_processor_with_ios_profile_rejects_non_positional_swap():
    api = MagicMock()
    api.translate_batch.side_effect = lambda texts, *a, **k: [_swap_two_tokens(transliterate(t)) for t in texts]
    processor = BatchProcessor(api, batch_size=10, max_parallel_batches=1, provider="algebras-ai")
    texts = ["%1$@ shared %2$d files", "%@ sent %d photos", "Total: %.2f"]
    result = processor.process(texts, "en", "uz", False, "", placeholder_profile=P)

    assert result.failed_indices == {1}
    assert "%2$d" in result.translations[0] and "%1$@" in result.translations[0]
    assert result.translations[0].index("%2$d") < result.translations[0].index("%1$@")
    assert "%.2f" in result.translations[2]


@pytest.fixture
def ios_project(tmp_path, monkeypatch):
    (tmp_path / "App" / "en.lproj").mkdir(parents=True)
    (tmp_path / "App" / "uz.lproj").mkdir(parents=True)
    (tmp_path / "App" / "en.lproj" / "Localizable.strings").write_text(SOURCE_STRINGS, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "uz"],
                "source_files": {
                    "App/en.lproj/Localizable.strings": {
                        "destination_path": "App/%algebras_locale_code%.lproj/Localizable.strings"
                    }
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_translate_end_to_end_keeps_placeholders(ios_project, monkeypatch):
    sent = []

    def fake_translate_batch(self, texts, *args, **kwargs):
        sent.extend(texts)
        return [_swap_two_tokens(transliterate(t)) for t in texts]

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", fake_translate_batch)
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)

    translate_command.execute(language="uz", force="__all__")

    # The model never saw a specifier or a tag.
    assert sent and not any("%" in t or "<a" in t for t in sent)

    target_file = ios_project / "App" / "uz.lproj" / "Localizable.strings"
    source = read_ios_strings_file(str(ios_project / "App" / "en.lproj" / "Localizable.strings"))
    target = read_ios_strings_file(str(target_file))

    # The non-positional swap was rejected: the key is left out, so 'status' reports it as missing.
    assert "sent_by" not in target
    assert set(target) == set(source) - {"sent_by"}
    for key, value in target.items():
        assert verify(source[key], value, P) == [], key
        assert value != source[key], key  # translated
    assert target["files_shared"].index("%2$d") < target["files_shared"].index("%1$@")
    assert target["discount"].count("%%") == 1
    assert '<a href="%@">' in target["link"] and "</a>" in target["link"]
    raw = target_file.read_text(encoding="utf-8")
    assert '\\"' in raw and "\\n" in raw  # quotes and newline escaped on write
    assert "%1$@" in raw and "%.2f" in raw and "%ld" in raw


# ---------------------------------------------------------------------------
# 'algebras placeholders' check and --fix
# ---------------------------------------------------------------------------

TARGET_STRINGS = r"""/* Greeting shown on the home screen */
"welcome_user" = "Хуш келибсиз, ％＠!";

// Two arguments; positional, so translations may reorder them
"files_shared" = "%2$д та файлни %1$ @ улашди";
"total_price"   =   "Жами: %.2ф";
"discount" = "Бугун 20%% тежанг";
"quote" = "Давом этиш учун \"Continue\" ни босинг\nКейинги қатор";
"link" = "<a href=\"%@\">Шартлар</a>ни ўқинг";
"items_count" = "%d та элемент";
"sent_by" = "%@ %d та расм юборди";
"plain" = "Салом";
"""

FIXED_STRINGS = r"""/* Greeting shown on the home screen */
"welcome_user" = "Хуш келибсиз, %@!";

// Two arguments; positional, so translations may reorder them
"files_shared" = "%2$d та файлни %1$@ улашди";
"total_price"   =   "Жами: %.2f";
"discount" = "Бугун 20%% тежанг";
"quote" = "Давом этиш учун \"Continue\" ни босинг\nКейинги қатор";
"link" = "<a href=\"%@\">Шартлар</a>ни ўқинг";
"items_count" = "%ld та элемент";
"sent_by" = "%@ %d та расм юборди";
"plain" = "Салом";
"""


@pytest.fixture
def corrupted_project(ios_project):
    target = ios_project / "App" / "uz.lproj" / "Localizable.strings"
    target.write_text(TARGET_STRINGS, encoding="utf-8")
    return target


def test_check_reports_corruptions(corrupted_project, capsys):
    assert placeholders_command.execute(output_format="json") == 1
    report = json.loads(capsys.readouterr().out)
    issues = {i["key"]: i for i in report["issues"]}
    assert set(issues) == {"welcome_user", "files_shared", "total_price", "items_count"}
    codes = {k: {p["code"] for p in v["problems"]} for k, v in issues.items()}
    assert codes["welcome_user"] == {"missing", "corrupted"}
    assert codes["files_shared"] == {"missing", "corrupted"}
    assert codes["items_count"] == {"missing", "extra"}  # %d vs %ld
    assert issues["files_shared"]["fixed"] == "%2$d та файлни %1$@ улашди"


def test_fix_in_place_then_clean_and_idempotent(corrupted_project, capsys):
    assert placeholders_command.execute(fix=True) == 0
    assert corrupted_project.read_text(encoding="utf-8") == FIXED_STRINGS

    assert placeholders_command.execute() == 0

    before = corrupted_project.read_bytes()
    assert placeholders_command.execute(fix=True) == 0
    assert corrupted_project.read_bytes() == before


def test_dry_run_writes_nothing(corrupted_project, capsys):
    assert placeholders_command.execute(fix=True, dry_run=True) == 1
    assert corrupted_project.read_text(encoding="utf-8") == TARGET_STRINGS
    assert "Would fix 4 value(s)" in capsys.readouterr().out


def test_non_positional_reorder_is_reported_not_fixed(corrupted_project, capsys):
    corrupted_project.write_text(
        FIXED_STRINGS.replace('"%@ %d та расм юборди"', '"%d та расмни %@ юборди"'), encoding="utf-8"
    )
    assert placeholders_command.execute(fix=True, output_format="json") == 2
    report = json.loads(capsys.readouterr().out)
    assert [(i["key"], i["status"], i["problems"][0]["code"]) for i in report["issues"]] == [
        ("sent_by", "unresolved", "reordered")
    ]


# ---------------------------------------------------------------------------
# In-place writer
# ---------------------------------------------------------------------------


def test_in_place_update_touches_only_given_keys(tmp_path):
    path = tmp_path / "Localizable.strings"
    original = (
        '/* header "x" = "y"; */\r\n'
        '"b" = "B %@";\r\n'
        '"a"="A";   // trailing "a" = "z";\r\n'
        '"it\'s" = "don\'t \\"touch\\"";\r\n'
    )
    path.write_bytes(original.encode("utf-8"))

    update_ios_strings_file_in_place(str(path), {"a": 'New "A" %1$@\n', "missing": "ignored"})

    expected = original.replace('"a"="A";', '"a"="New \\"A\\" %1$@\\n";')
    assert path.read_bytes() == expected.encode("utf-8")
    assert read_ios_strings_file(str(path))["a"] == 'New "A" %1$@\n'


def test_fix_writer_maps_key_paths(tmp_path):
    path = tmp_path / "uz.lproj" / "Localizable.strings"
    path.parent.mkdir()
    path.write_text('"k" = "%д";\n"o" = "x";\n', encoding="utf-8")
    get_fix_writer(str(path))(str(path), {("k",): "%d"}, "uz", None)
    assert path.read_text(encoding="utf-8") == '"k" = "%d";\n"o" = "x";\n'
