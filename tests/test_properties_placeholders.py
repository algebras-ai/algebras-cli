"""
Java .properties placeholder safety: MessageFormat arguments, choice syntax, apostrophes, printf and
${…} survive translation; damaged files are reported and repaired in place by 'algebras placeholders'.
"""

import json
import os
import re

import pytest

from algebras.commands import healthcheck_command, placeholders_command
from algebras.commands.translate_command import (
    _load_file_contents,
    _translate_plural_aware,
    _write_translated_content,
)
from algebras.services.placeholders import extract, mask, profile_for_path, unmask, verify
from algebras.services.placeholders.file_checks import get_file_check
from algebras.services.placeholders.fix_writers import get_fix_writer
from algebras.services.placeholders.formats.properties import (
    PROPERTIES_PROFILE,
    apostrophe_problems,
    fix_apostrophes,
    repair_value,
    value_problems,
)
from algebras.services.translator import Translator
from algebras.utils.file_format_detector import FileFormat, detect_format
from algebras.utils.file_format_handlers import PropertiesHandler, get_handler
from algebras.utils.lang_validator import read_language_file
from algebras.utils.properties_handler import read_properties_file, update_properties_values

from tests.test_placeholders_translation import transliterate
from tests.test_stringsdict_plurals import _batch_response, _mock_config

P = PROPERTIES_PROFILE


# --- a tiny java.text.MessageFormat, to check what Java would print ------------------------


def _choice(style: str, value):
    """ChoiceFormat: pick the sub-message for `value` (quotes: '' -> ', '…' quoted)."""
    segments, limit, text, in_quote, part = [], "", "", False, 0
    i = 0
    while i < len(style):
        c = style[i]
        if c == "'":
            if i + 1 < len(style) and style[i + 1] == "'":
                if part:
                    text += "'"
                i += 2
                continue
            in_quote = not in_quote
        elif in_quote:
            text += c
        elif part == 0 and c in "#<":
            segments.append([float(limit), c])
            part = 1
        elif c == "|":
            segments[-1].append(text)
            limit, text, part = "", "", 0
        elif part:
            text += c
        else:
            limit += c
        i += 1
    segments[-1].append(text)
    chosen = segments[0][2]
    for lim, op, msg in segments:
        if value > lim or (op == "#" and value == lim):
            chosen = msg
    return chosen


def java_format(pattern: str, *args) -> str:
    """java.text.MessageFormat.format for {n}, {n,number…} and {n,choice,…}."""
    out, i, in_quote = "", 0, False
    while i < len(pattern):
        c = pattern[i]
        if c == "'":
            if i + 1 < len(pattern) and pattern[i + 1] == "'":
                out += "'"
                i += 2
                continue
            in_quote = not in_quote
            i += 1
        elif c == "{" and not in_quote:
            depth, j, q = 0, i + 1, False
            while True:  # in-brace quotes are copied verbatim
                ch = pattern[j]
                if q:
                    q = ch != "'"
                elif ch == "'":
                    q = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    if depth == 0:
                        break
                    depth -= 1
                j += 1
            parts = pattern[i + 1 : j].split(",", 2)
            value = args[int(parts[0])]
            if len(parts) == 3 and parts[1].strip() == "choice":
                sub = _choice(parts[2], value)
                out += java_format(sub, *args) if "{" in sub else sub
            else:
                out += str(value)
            i = j + 1
        else:
            out += c
            i += 1
    return out


def test_java_format_model():
    assert java_format("Don''t delete {0}", "x") == "Don't delete x"
    assert java_format("L'utilisateur {0}", "x") == "Lutilisateur {0}"  # the bug
    assert java_format("{0,choice,0#no files|1#one file|1<{0} files}", 3) == "3 files"
    assert java_format("{0,choice,0#n''a|1<{0} d''''abord}", 0) == "n'a"
    assert java_format("{0,choice,0#n''a|1<{0} d''''abord}", 2) == "2 d'abord"


# --- registration and file handling -------------------------------------------------------


def test_properties_is_a_registered_format(tmp_path):
    path = str(tmp_path / "messages.properties")
    assert detect_format(path) == FileFormat.PROPERTIES
    assert isinstance(get_handler(path), PropertiesHandler)
    assert get_file_check(path) is not None
    assert get_fix_writer(path) is not None


RAW_SOURCE = (
    "# Greetings\n"
    "! old-style comment\n"
    "welcome=Welcome, {0}!\n"
    "price={0,number,#.##} \\u20AC\n"
    "files={0,choice,0#no files|1#one file|1<{0,number,integer} files}\n"
    "msg=Don''t delete {0}\n"
    "path\\:key = C\\:\\\\temp\\=x\n"
    "long=This is a long \\\n"
    "    message for {0}\n"
    "count=%1$d new for ${user.name}\n"
    "plain=It's fine\n"
)


@pytest.fixture
def source_file(tmp_path):
    path = tmp_path / "messages.properties"
    path.write_text(RAW_SOURCE, encoding="utf-8")
    return str(path)


def test_reader_follows_java_properties_rules(source_file):
    data = read_properties_file(source_file)
    assert data == {
        "welcome": "Welcome, {0}!",
        "price": "{0,number,#.##} €",
        "files": "{0,choice,0#no files|1#one file|1<{0,number,integer} files}",
        "msg": "Don''t delete {0}",
        "path:key": "C:\\temp=x",
        "long": "This is a long message for {0}",
        "count": "%1$d new for ${user.name}",
        "plain": "It's fine",
    }
    assert read_language_file(source_file) == data


def test_profile_is_detected_per_file(source_file, tmp_path):
    assert profile_for_path(source_file).syntax_names == ("messageformat", "java_printf", "js_template")
    only_mf = tmp_path / "other.properties"
    only_mf.write_text("a=Hi {0}\nb=50% off\n", encoding="utf-8")
    assert profile_for_path(str(only_mf)).syntax_names == ("messageformat",)


def test_update_in_place_keeps_comments_order_and_continuations(tmp_path):
    path = tmp_path / "messages_fr.properties"
    original = (
        "# Comment\n"
        "a = un\n"
        "long=Ceci est un long \\\n"
        "    message pour l'{0}\n"
        "b:deux\n"
    )
    path.write_text(original, encoding="utf-8")
    assert update_properties_values(str(path), {"long": "Ceci est un long message pour l''{0}"}, add_missing=False) == []
    assert path.read_text(encoding="utf-8") == original.replace("l'{0}", "l''{0}")
    update_properties_values(str(path), {"c": "trois"})
    assert path.read_text(encoding="utf-8").endswith("b:deux\nc=trois\n")


def test_unicode_escape_files_stay_ascii(tmp_path):
    path = tmp_path / "messages_ru.properties"
    path.write_text("a=\\u041F\\u0440\\u0438\\u0432\\u0435\\u0442 {0}\n", encoding="utf-8")
    update_properties_values(str(path), {"b": "Пока, {0}!"})
    text = path.read_text(encoding="utf-8")
    assert text.isascii()
    assert "b=\\u041F\\u043E\\u043A\\u0430, {0}!" in text
    assert read_properties_file(str(path))["b"] == "Пока, {0}!"


# --- extraction and the apostrophe codec --------------------------------------------------


def test_messageformat_pieces_are_masked():
    assert mask("price={0,number,#.##} €", P).text == "price=⟦0⟧ €"
    choice = mask("{0,choice,0#no files|1#one file|1<{0,number,integer} files}", P)
    assert choice.text == "⟦0⟧no files⟦1⟧one file⟦2⟧⟦3⟧ files⟦4⟧"
    assert [p.raw for p in extract("Use '{' or '{0}', it''s {1} %s ${x}", P)] == [
        "'{'", "'{0}'", "{1}", "%s", "${x}",
    ]


def test_apostrophes_are_undoubled_for_the_model_and_doubled_back():
    m = mask("Don''t delete {0}", P)
    assert m.text == "Don't delete ⟦0⟧"
    assert unmask("N'effacez pas l'élément ⟦0⟧", m, P) == "N''effacez pas l''élément {0}"

    m = mask("Welcome, {0}!", P)  # MessageFormat because of {0}, even without apostrophes
    assert unmask("L'utilisateur ⟦0⟧ est là", m, P) == "L''utilisateur {0} est là"

    m = mask("Don''t", P)  # no arguments, but '' marks MessageFormat
    assert m.text == "Don't" and unmask("N'effacez pas", m, P) == "N''effacez pas"

    m = mask("It's ${name}", P)  # not MessageFormat: apostrophes stay as they are
    assert m.text == "It's ⟦0⟧" and unmask("C'est ⟦0⟧", m, P) == "C'est ${name}"


def test_choice_sub_messages_get_their_own_quoting():
    source = "{0,choice,0#no files|1<{0} files}"
    m = mask(source, P)
    out = unmask("⟦0⟧pas d'fichier⟦1⟧⟦2⟧ fichiers d'abord⟦3⟧", m, P)
    assert out == "{0,choice,0#pas d''fichier|1<{0} fichiers d''''abord}"
    assert java_format(out, 0) == "pas d'fichier"
    assert java_format(out, 5) == "5 fichiers d'abord"


def test_intentional_quotes_are_kept():
    m = mask("Type '{0}' to insert {0}", P)
    out = unmask("Tapez ⟦0⟧ pour l'insérer ⟦1⟧", m, P)
    assert out == "Tapez '{0}' pour l''insérer {0}"
    assert java_format(out, "X") == "Tapez {0} pour l'insérer X"


# --- translation end to end ---------------------------------------------------------------


def _fake_api(sent, answer):
    def post(url, headers=None, json=None, **kwargs):
        sent.append(json)
        return _batch_response([answer(t) for t in json["texts"]])

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
    missing = [k for k in source_content if k not in target_content]
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
        target, translated, handler, set(missing), os.path.exists(target),
        source_file=source, source_language="en", target_language=lang,
        source_raw_content=source_raw, target_raw_content=target_raw,
    )
    return [t for body in sent for t in body["texts"]]


def _french(text: str) -> str:
    """A translator that adds apostrophes everywhere."""
    for en, fr in (
        ("Welcome,", "Bienvenue à l'utilisateur"),
        ("Don't delete", "N'effacez pas l'élément"),
        ("no files", "pas d'fichier"),
        ("one file", "un fichier d'abord"),
        (" files", " fichiers d'abord"),
        ("This is a long message for", "Message long pour l'ami"),
        ("new for", "nouveaux pour l'équipe"),
    ):
        text = text.replace(en, fr)
    return text


def test_french_apostrophes_never_swallow_arguments(source_file, monkeypatch):
    target = os.path.join(os.path.dirname(source_file), "messages_fr.properties")
    sent = _translate(source_file, target, "fr", monkeypatch, _french)

    # The model never sees MessageFormat syntax, printf or ${…}, and gets plain apostrophes.
    for t in sent:
        assert "{" not in t and "%" not in t and "''" not in t, t
    assert "Don't delete ⟦0⟧" in sent

    written = read_properties_file(target)
    source = read_properties_file(source_file)
    assert written["welcome"] == "Bienvenue à l''utilisateur {0}!"
    assert written["msg"] == "N''effacez pas l''élément {0}"
    assert written["price"] == "{0,number,#.##} €"
    assert written["files"] == (
        "{0,choice,0#pas d''fichier|1#un fichier d''abord|1<{0,number,integer} fichiers d''''abord}"
    )
    assert written["count"] == "%1$d nouveaux pour l'équipe ${user.name}" or "%1$d" in written["count"]
    assert "''" not in written["count"]  # not MessageFormat: Java prints it as written

    assert java_format(written["welcome"], "Ann") == "Bienvenue à l'utilisateur Ann!"
    assert java_format(written["msg"], "x") == "N'effacez pas l'élément x"
    assert java_format(written["files"], 0) == "pas d'fichier"
    assert java_format(written["files"], 1) == "un fichier d'abord"
    assert java_format(written["long"], "Ann") == "Message long pour l'ami Ann"
    for key in source:
        assert value_problems(source[key], written[key], profile_for_path(source_file)) == [], key


@pytest.mark.parametrize("lang", ["ru", "uz-Cyrl"])
def test_non_ascii_target_with_unicode_escapes_keeps_placeholders(source_file, monkeypatch, lang):
    target = os.path.join(os.path.dirname(source_file), f"messages_{lang}.properties")
    with open(target, "w", encoding="utf-8") as f:
        f.write("# translated\nplain=\\u0425\\u043E\\u0440\\u043E\\u0448\\u043E\n")
    _translate(source_file, target, lang, monkeypatch, transliterate)

    text = open(target, encoding="utf-8").read()
    assert text.isascii() and "\\u" in text  # the file keeps its \uXXXX convention
    assert text.startswith("# translated\n")
    # The existing entry stays as written; new keys go to their source position (before it).
    assert text.endswith("\nplain=\\u0425\\u043E\\u0440\\u043E\\u0448\\u043E\n")
    written = read_properties_file(target)
    assert "{0}" in written["welcome"] and re.search("[А-я]", written["welcome"])
    assert written["price"].startswith("{0,number,#.##}")
    assert "%1$d" in written["count"] and "${user.name}" in written["count"]
    assert "{0,choice,0#" in written["files"] and "|1<{0,number,integer}" in written["files"]
    source = read_properties_file(source_file)
    for key in source:
        assert value_problems(source[key], written[key], profile_for_path(source_file)) == [], key


def test_new_target_file_is_written_with_unicode_escapes(source_file, monkeypatch):
    target = os.path.join(os.path.dirname(source_file), "messages_ru.properties")
    _translate(source_file, target, "ru", monkeypatch, transliterate)
    text = open(target, encoding="utf-8").read()
    assert text.isascii()
    assert list(read_properties_file(target)) == list(read_properties_file(source_file))


# --- check + autofix ----------------------------------------------------------------------


SOURCE_FILE = (
    "welcome=Welcome, {0}!\n"
    "price={0,number,#.##} \\u20AC\n"
    "files={0,choice,0#no files|1#one file|1<{0,number,integer} files}\n"
    "msg=Don''t delete {0}\n"
    "delete=Delete {0}?\n"
    "long=This is a long \\\n"
    "    message for {0}\n"
    "count=%1$d new\n"
)

TARGET_FILE = (
    "# French\n"
    "welcome=Bienvenue, {0} !\n"
    "price={0,nombre,#.##} \\u20AC\n"
    "files={0,choice,0#aucun fichier|1#un fichier|1<{0,number,integer} fichiers}\n"
    "msg={0} : n'effacez pas\n"
    "delete=Supprimer l'\\u00E9l\\u00E9ment {0} ?\n"
    "long=Ceci est un long \\\n"
    "    message pour l'{0}\n"
    "count=%1$д nouveaux\n"
)

EXPECTED_FILE = (
    TARGET_FILE.replace("{0,nombre,", "{0,number,")
    .replace("n'effacez", "n''effacez")
    .replace("l'\\u00E9", "l''\\u00E9")
    .replace("l'{0}", "l''{0}")
    .replace("%1$д", "%1$d")
)


@pytest.fixture
def check_project(tmp_path, monkeypatch):
    res = tmp_path / "src" / "main" / "resources"
    res.mkdir(parents=True)
    (res / "messages.properties").write_text(SOURCE_FILE, encoding="utf-8")
    (res / "messages_fr.properties").write_text(TARGET_FILE, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "fr"],
                "source_files": {
                    "src/main/resources/messages.properties": {
                        "destination_path": "src/main/resources/messages_%algebras_locale_code%.properties"
                    }
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return res / "messages_fr.properties"


def _report(capsys):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json")
    return code, json.loads(capsys.readouterr().out)


def test_check_reports_exact_codes(check_project, capsys):
    code, report = _report(capsys)
    assert code == 1
    assert report["files_checked"] == 1
    codes = {i["key"]: sorted({p["code"] for p in i["problems"]}) for i in report["issues"]}
    assert codes == {
        "price": ["mf_type_changed"],
        "msg": ["mf_apostrophe"],
        "delete": ["mf_arg_quoted"],
        "long": ["mf_arg_quoted"],
        "count": ["corrupted", "missing"],
    }
    assert all(i["fixed"] is not None for i in report["issues"])


def test_fix_repairs_in_place_and_is_idempotent(check_project, capsys):
    assert placeholders_command.execute(fix=True, output_format="json") == 0
    assert check_project.read_text(encoding="utf-8") == EXPECTED_FILE  # comments, \u, continuation kept

    code, report = _report(capsys)
    assert code == 0 and report["issues"] == []

    placeholders_command.execute(fix=True, output_format="json")
    assert check_project.read_text(encoding="utf-8") == EXPECTED_FILE

    fixed = read_properties_file(str(check_project))
    assert java_format(fixed["delete"], "X") == "Supprimer l'élément X ?"
    assert java_format(fixed["long"], "X") == "Ceci est un long message pour l'X"


def test_dry_run_writes_nothing(check_project):
    assert placeholders_command.execute(fix=True, dry_run=True, output_format="json") == 1
    assert check_project.read_text(encoding="utf-8") == TARGET_FILE


def test_healthcheck_covers_properties(check_project):
    issues, keys_checked, errors, _ = healthcheck_command.validate_file_pair(
        "src/main/resources/messages.properties", "src/main/resources/messages_fr.properties", "en", "fr", None, False
    )
    assert keys_checked == 7
    assert "system" not in {i.category for i in issues}
    assert {"price", "count"} <= {i.key for i in issues if i.category == "placeholders"}


def test_pairing_with_and_without_language_suffix(tmp_path):
    base = tmp_path / "messages.properties"
    base.write_text("a=b\n", encoding="utf-8")
    target = str(tmp_path / "messages_ru.properties")
    assert healthcheck_command.find_source_file(target, [], "en", "ru") == str(base)
    with_suffix = str(tmp_path / "messages_en.properties")
    assert healthcheck_command.find_source_file(target, [with_suffix], "en", "ru") == with_suffix


# --- repair unit cases --------------------------------------------------------------------


def test_type_and_style_are_restored_by_index():
    source = "Total {0,number,#.##} on {1,date,short}"
    target = "Итого {0,число,#,##} на {1,дата,short}"
    assert {p.code for p in value_problems(source, target, P)} == {"mf_type_changed"}
    assert repair_value(source, target, P) == "Итого {0,number,#.##} на {1,date,short}"


def test_two_quoted_arguments_are_both_freed():
    problems = apostrophe_problems("The {0} and the {1}", "L'{0} et l'{1}")
    assert [p.code for p in problems] == ["mf_arg_quoted"]
    assert repair_value("The {0} and the {1}", "L'{0} et l'{1}", P) == "L''{0} et l''{1}"


def test_fix_apostrophes_keeps_source_quotes_and_is_idempotent():
    source = "Type '{0}' for {0}"
    once = fix_apostrophes(source, "Tapez '{0}' pour l'{0}")
    assert once == "Tapez '{0}' pour l''{0}"
    assert fix_apostrophes(source, once) == once
    assert value_problems(source, once, P) == []


def test_clean_targets_have_no_problems():
    assert value_problems("Don''t delete {0}", "N''effacez pas {0}", P) == []
    assert value_problems("It's {0}", "C''est {0}", P) == []
    assert verify("Hi ${name}", "Salut ${name}", P) == []
