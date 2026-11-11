"""
YAML placeholder protection: Rails (%{name}, %<price>.2f, plural hashes, *_html), Symfony (%count%),
profile auto-detection, writer quoting, translation end to end with a transliterating model, and
'algebras placeholders' check / --fix (in place, comments kept, idempotent).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from algebras.commands import placeholders_command, translate_command
from algebras.services.placeholders import extract, mask, profile_for_path
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import yaml_format
from algebras.utils.file_format_handlers.yaml_handler import YAMLHandler


@pytest.fixture(autouse=True)
def yaml_fix_writer():
    # Other tests may replace writers with recording ones; use the real one here.
    register_fix_writer([".yaml", ".yml"], yaml_format.write_fixes)
    yield


RAILS_EN = """\
# Storefront strings
en:
  greeting: "Hello, %{name}!"
  unread: "%{count} unread"
  price: "Price: %<price>.2f"
  welcome_html: "Welcome back, <b>%{name}</b>! <a href=\\"/inbox\\">Open inbox</a>"
  confirm: "Yes"
  inbox:
    # Rails plural hash
    messages:
      one: "One message"
      other: "%{count} messages"
    title: Inbox
"""

SYMFONY_EN = """\
# Symfony translations
cart:
  items: "%count% items in your cart"
  greeting: "Hello %name%, you have %count% new messages"
validators:
  too_long: "This value is too long. It should have {{ limit }} characters or less."
"""


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Profile detection
# ---------------------------------------------------------------------------


def test_rails_profile_from_locale_root(tmp_path):
    source = _write(tmp_path / "config" / "locales" / "en.yml", RAILS_EN)
    profile = profile_for_path(str(source))
    assert profile.syntax_names[0] == "ruby"
    assert "xml_tag" in profile.syntax_names  # *_html markup
    raws = [p.raw for p in extract("Price: %<price>.2f for %{name}", profile)]
    assert raws == ["%<price>.2f", "%{name}"]
    masked = mask('Welcome back, <b>%{name}</b>! <a href="/inbox">Open inbox</a>', profile)
    assert masked.text == "Welcome back, ⟦0⟧⟦1⟧⟦2⟧! ⟦3⟧Open inbox⟦4⟧"


def test_rails_profile_from_percent_brace_without_root(tmp_path):
    source = _write(tmp_path / "locales" / "app.yml", "a: 'Hi %{name}'\n")
    assert profile_for_path(str(source)).syntax_names == ("ruby",)


def test_symfony_profile_by_name_and_directory(tmp_path):
    messages = _write(tmp_path / "app" / "messages.en.yaml", SYMFONY_EN)
    profile = profile_for_path(str(messages))
    assert profile.syntax_names[0] == "symfony"
    assert [p.raw for p in extract("Hello %name%, you have %count% new", profile)] == ["%name%", "%count%"]
    assert [p.raw for p in extract("at most {{ limit }} characters", profile)] == ["{{ limit }}"]
    # 50% off is not a placeholder
    assert extract("50% off, 20% more", profile) == []

    in_dir = _write(tmp_path / "translations" / "validators.en.yaml", "x: '%limit% max'\n")
    assert profile_for_path(str(in_dir)).syntax_names[0] == "symfony"


def test_icu_profile_for_intl_icu_files(tmp_path):
    source = _write(
        tmp_path / "translations" / "messages+intl-icu.en.yaml",
        "items: '{count, plural, one {# item} other {# items}} for {name}'\n",
    )
    profile = profile_for_path(str(source))
    assert profile.syntax_names[0] in ("arb_icu", "icu_simple")
    assert "symfony" not in profile.syntax_names


def test_generic_profile_by_frequency(tmp_path):
    source = _write(tmp_path / "locales" / "en.yaml", "hi: 'Hello {{name}}'\nbye: Bye {{name}}\n")
    assert profile_for_path(str(source)).syntax_names == ("i18next",)


# ---------------------------------------------------------------------------
# Plural groups
# ---------------------------------------------------------------------------

GROUP = {"one": "One message", "other": "%{count} messages"}


def test_plural_group_detection():
    assert yaml_format.is_plural_group(GROUP)
    assert yaml_format.is_plural_group({"zero": "None", "one": "1", "other": "%{count}"})
    assert not yaml_format.is_plural_group({"one": "x", "two": "y"})  # no 'other'
    assert not yaml_format.is_plural_group({"one": "x", "other": "y", "title": "z"})
    data = yaml.safe_load(RAILS_EN)
    assert yaml_format.find_plural_groups(data) == [(("en", "inbox", "messages"), GROUP)]


def test_plural_source_text_follows_the_target_language(tmp_path):
    profile = profile_for_path(str(_write(tmp_path / "en.yml", RAILS_EN)))
    # German one = 1 only: keeps "One message". Russian one = 1, 21, 31 …: needs %{count}.
    assert yaml_format.plural_source_text(GROUP, "one", "de", profile) == "One message"
    assert yaml_format.plural_source_text(GROUP, "one", "ru", profile) == "%{count} messages"
    assert yaml_format.plural_source_text(GROUP, "few", "ru", profile) == "%{count} messages"

    expanded, contexts = yaml_format.prepare_for_translation(yaml.safe_load(RAILS_EN), "en", "ru", profile)
    assert list(expanded["en"]["inbox"]["messages"]) == ["one", "few", "many", "other"]
    assert set(expanded["en"]["inbox"]["messages"].values()) == {"%{count} messages"}
    assert expanded["en"]["inbox"]["title"] == "Inbox"
    assert set(contexts) == {f"en.inbox.messages.{f}" for f in ("one", "few", "many", "other")}
    assert "%{count}" in contexts["en.inbox.messages.few"]


# ---------------------------------------------------------------------------
# Writer quoting
# ---------------------------------------------------------------------------

TRICKY_VALUES = [
    "%{count} items",
    "%<price>.2f total",
    "{name} joined",
    "{{name}} joined",
    "%count% items",
    "{0}",
    "@mention",
    "yes",
    "123",
    "- dash",
    "a: b",
    "a #b",
    "'quoted'",
    "multi\nline %{x}",
]


def test_translation_writer_quotes_values_that_start_with_a_placeholder(tmp_path):
    target = tmp_path / "ru.yml"
    content = {"ru": {f"k{i}": v for i, v in enumerate(TRICKY_VALUES)}}
    YAMLHandler().write(str(target), content)
    text = target.read_text(encoding="utf-8")
    assert "k0: '%{count} items'" in text
    assert "k2: '{name} joined'" in text
    assert yaml.safe_load(text) == content


@pytest.mark.parametrize("style", [None, "'", '"'])
def test_fix_renderer_round_trips(style):
    for value in TRICKY_VALUES + ["plain text", "Привет, %{name}!", "it's"]:
        rendered = yaml_format.render_scalar(value, style)
        assert yaml.safe_load(f"k: {rendered}") == {"k": value}, (style, value, rendered)
    assert yaml_format.render_scalar("plain text", None) == "plain text"
    assert yaml_format.render_scalar("%{count} шт.", None) == "'%{count} шт.'"


# ---------------------------------------------------------------------------
# Translation end to end
# ---------------------------------------------------------------------------

_LATIN_TO_CYRILLIC = str.maketrans(dict(zip("sdcSDabeiklmnoprtuvxyz", "сдсСДабеиклмнопртувхйз")))


def transliterate(text: str) -> str:
    """What the model did for uz-Cyrl: every Latin letter becomes Cyrillic (tokens survive)."""
    return text.translate(_LATIN_TO_CYRILLIC)


def _fake_client(sent):
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        sent.append((list(texts), list(kwargs.get("contexts") or [])))
        return [transliterate(t) for t in texts]

    client.translate_batch.side_effect = translate_batch
    return client


def _project(tmp_path, monkeypatch, source_rel, source_text, destination, languages):
    _write(tmp_path / source_rel, source_text)
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": languages,
                "source_files": {source_rel: {"destination_path": destination}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")


def _translate(languages, sent, **kwargs):
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        for language in languages:
            translate_command.execute(language=language, **kwargs)


RAILS_LANGUAGES = ["en", "ru", "de", {"uz-Cyrl": "uz_Cyrl"}]


def test_rails_translation_keeps_every_placeholder(tmp_path, monkeypatch):
    _project(
        tmp_path, monkeypatch, "config/locales/en.yml", RAILS_EN,
        "config/locales/%algebras_locale_code%.yml", RAILS_LANGUAGES,
    )
    sent = []
    _translate(["ru", "de", "uz-Cyrl"], sent, force="__all__")

    source = tmp_path / "config" / "locales" / "en.yml"
    for locale, forms in (("ru", ["one", "few", "many", "other"]), ("de", ["one", "other"]), ("uz_Cyrl", ["one", "other"])):
        path = tmp_path / "config" / "locales" / f"{locale}.yml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))  # re-parses
        body = data["en"]
        assert body["greeting"].count("%{name}") == 1
        assert body["unread"].startswith("%{count}")  # survived quoting
        assert "%<price>.2f" in body["price"]
        assert body["welcome_html"].count("<b>%{name}</b>") == 1 and '<a href="/inbox">' in body["welcome_html"]
        assert isinstance(body["confirm"], str)
        group = body["inbox"]["messages"]
        assert sorted(group) == sorted(forms)
        for form, text in group.items():
            if form == "one" and locale != "ru":
                assert "%{count}" not in text  # one = 1 only: "One message"
            else:
                assert "%{count}" in text, (locale, form, text)
        # The same check 'algebras placeholders' runs.
        lang = locale.replace("_", "-")
        assert yaml_format.check_file(str(source), str(path), "en", lang) == []

    # The model never saw a raw placeholder or tag, and plural forms had their notes.
    assert not any("%{" in t or "%<" in t or "<b>" in t for texts, _ in sent for t in texts)
    assert any(c and "Plural form 'few' for Russian" in c for _, contexts in sent for c in contexts)


def test_rails_missing_plural_forms_are_added_with_only_missing(tmp_path, monkeypatch):
    _project(
        tmp_path, monkeypatch, "config/locales/en.yml", RAILS_EN,
        "config/locales/%algebras_locale_code%.yml", ["en", "ru"],
    )
    target = _write(
        tmp_path / "config" / "locales" / "ru.yml",
        "en:\n  greeting: 'Привет, %{name}!'\n",
    )
    sent = []
    _translate(["ru"], sent, only_missing=True)
    data = yaml.safe_load(target.read_text(encoding="utf-8"))["en"]
    assert data["greeting"] == "Привет, %{name}!"
    assert sorted(data["inbox"]["messages"]) == ["few", "many", "one", "other"]
    assert all("%{count}" in t for t in data["inbox"]["messages"].values())


def test_symfony_translation_keeps_percent_placeholders(tmp_path, monkeypatch):
    _project(
        tmp_path, monkeypatch, "translations/messages.en.yaml", SYMFONY_EN,
        "translations/messages.%algebras_locale_code%.yaml", ["en", "ru"],
    )
    sent = []
    _translate(["ru"], sent, force="__all__")
    path = tmp_path / "translations" / "messages.ru.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["cart"]["items"].startswith("%count% ")
    assert "%name%" in data["cart"]["greeting"] and "%count%" in data["cart"]["greeting"]
    assert "{{ limit }}" in data["validators"]["too_long"]
    assert not any("%count%" in t or "{{" in t for texts, _ in sent for t in texts)


# ---------------------------------------------------------------------------
# 'algebras placeholders'
# ---------------------------------------------------------------------------

CORRUPTED_RU = """\
# Storefront strings (ru)
en:
  greeting: "Привет, %{имя}!"
  unread: '%{ count } непрочитанных'
  price: "Цена: %<цена>.2f"
  welcome_html: "С возвращением, <b>% {name}</b>! <a href=\\"/inbox\\">Открыть</a>"
  confirm: yes
  inbox:
    # Rails plural hash
    messages:
      one: "%{count} сообщение"
      few: "%{соunt} сообщения"
      many: "%{count} сообщений"
      other: "%{count} сообщения"
    title: Входящие
"""

EXPECTED_FIXED = (
    CORRUPTED_RU.replace("%{имя}", "%{name}")
    .replace("'%{ count } непрочитанных'", "'%{count} непрочитанных'")
    .replace("%<цена>.2f", "%<price>.2f")
    .replace("% {name}", "%{name}")
    .replace("confirm: yes", "confirm: 'yes'")
    .replace("%{соunt}", "%{count}")
)


@pytest.fixture
def ru_project(tmp_path, monkeypatch):
    _project(
        tmp_path, monkeypatch, "config/locales/en.yml", RAILS_EN,
        "config/locales/%algebras_locale_code%.yml", ["en", "ru"],
    )
    return _write(tmp_path / "config" / "locales" / "ru.yml", CORRUPTED_RU)


def _report(capsys, **kwargs):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json", **kwargs)
    return code, json.loads(capsys.readouterr().out)


def test_check_reports_exact_codes(ru_project, capsys):
    code, report = _report(capsys)
    assert code == 1
    problems = {i["key"]: sorted(p["code"] for p in i["problems"]) for i in report["issues"]}
    assert problems == {
        "en.greeting": ["extra", "missing"],
        "en.unread": ["corrupted", "missing"],
        "en.price": ["extra", "missing"],
        "en.welcome_html": ["corrupted", "missing"],
        "en.confirm": ["yaml_type_coerced"],
        "en.inbox.messages.few": ["extra", "missing"],
    }
    assert all(i["fixed"] is not None for i in report["issues"])


def test_fix_repairs_in_place_keeps_comments_and_is_idempotent(ru_project, capsys):
    code, report = _report(capsys, fix=True)
    assert code == 0
    assert {i["status"] for i in report["issues"]} == {"fixed"}
    assert ru_project.read_text(encoding="utf-8") == EXPECTED_FIXED
    assert yaml.safe_load(EXPECTED_FIXED)["en"]["confirm"] == "yes"

    code, report = _report(capsys)
    assert (code, report["issues"]) == (0, [])

    code, report = _report(capsys, fix=True)
    assert code == 0
    assert ru_project.read_text(encoding="utf-8") == EXPECTED_FIXED


def test_dry_run_writes_nothing(ru_project, capsys):
    _report(capsys, fix=True, dry_run=True)
    assert ru_project.read_text(encoding="utf-8") == CORRUPTED_RU


def test_plural_single_count_exemption_and_missing_forms(tmp_path):
    source = _write(tmp_path / "en.yml", RAILS_EN)
    de = _write(
        tmp_path / "de.yml",
        "de:\n  inbox:\n    messages:\n      one: Eine Nachricht\n      other: '%{count} Nachrichten'\n",
    )
    assert yaml_format.check_file(str(source), str(de), "en", "de") == []

    # Russian one covers 1, 21, 31 …: the count must stay. few/many are missing.
    ru = _write(
        tmp_path / "ru.yml",
        "ru:\n  inbox:\n    messages:\n      one: Одно сообщение\n      other: '%{count} сообщения'\n",
    )
    findings = yaml_format.check_file(str(source), str(ru), "en", "ru")
    assert [(f.key, [p.code for p in f.problems], f.path) for f in findings] == [
        ("ru.inbox.messages.one", ["missing"], ("ru", "inbox", "messages", "one")),
        ("ru.inbox.messages.few", ["missing_form"], ("ru", "inbox", "messages", "few")),
        ("ru.inbox.messages.many", ["missing_form"], ("ru", "inbox", "messages", "many")),
    ]
    assert findings[0].source == "%{count} messages"
    assert all(f.fixed is None for f in findings)


def test_coerced_flow_mapping_is_quoted_back(tmp_path):
    source = _write(tmp_path / "locales" / "en.yaml", "title: '{name}'\nsub: 'Hi {name}'\n")
    target = _write(tmp_path / "locales" / "ru.yaml", "# keep me\ntitle: {name}\nsub: 'Привет {имя}'\n")
    findings = yaml_format.check_file(str(source), str(target), "en", "ru")
    assert [(f.key, [p.code for p in f.problems], f.fixed) for f in findings] == [
        ("title", ["yaml_type_coerced"], "{name}"),
        ("sub", ["missing", "corrupted"], "Привет {name}"),
    ]
    yaml_format.write_fixes(str(target), {f.path: f.fixed for f in findings})
    assert target.read_text(encoding="utf-8") == "# keep me\ntitle: '{name}'\nsub: 'Привет {name}'\n"


def test_symfony_transliterated_name_is_repaired(tmp_path):
    source = _write(tmp_path / "translations" / "messages.en.yaml", SYMFONY_EN)
    target = _write(
        tmp_path / "translations" / "messages.ru.yaml",
        SYMFONY_EN.replace('"%count% items in your cart"', '"%соунт% товаров в корзине"'),
    )
    findings = yaml_format.check_file(str(source), str(target), "en", "ru")
    assert [(f.key, sorted(p.code for p in f.problems), f.fixed) for f in findings] == [
        ("cart.items", ["corrupted", "missing"], "%count% товаров в корзине"),
    ]


def test_writer_handles_block_scalars_and_keeps_layout(tmp_path):
    target = _write(
        tmp_path / "ru.yml",
        "a:\n  # note\n  b: |\n    Привет %{имя}\n  c: plain\n",
    )
    yaml_format.write_fixes(str(target), {("a", "b"): "Привет %{name}\n"})
    text = target.read_text(encoding="utf-8")
    assert text == 'a:\n  # note\n  b: "Привет %{name}\\n"\n  c: plain\n'
    assert yaml.safe_load(text) == {"a": {"b": "Привет %{name}\n", "c": "plain"}}

    with pytest.raises(ValueError):
        yaml_format.write_fixes(str(target), {("a", "zz"): "x"})


def test_retranslate_adds_missing_plural_forms_per_key(tmp_path, monkeypatch, capsys):
    _project(
        tmp_path, monkeypatch, "config/locales/en.yml", RAILS_EN,
        "config/locales/%algebras_locale_code%.yml", ["en", "ru"],
    )
    target = _write(
        tmp_path / "config" / "locales" / "ru.yml",
        "en:\n  greeting: 'Привет, %{name}!'\n  inbox:\n    messages:\n"
        "      one: '%{count} сообщение'\n      other: '%{count} сообщения'\n",
    )
    sent = []
    capsys.readouterr()
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        code = placeholders_command.execute(output_format="json", fix=True, retranslate=True)
    out = capsys.readouterr().out
    report = json.loads(out[out.index("\n{\n") + 1 :])  # after the translate command's output
    assert code == 0
    assert {i["key"]: i["status"] for i in report["issues"]} == {
        "en.inbox.messages.few": "fixed",
        "en.inbox.messages.many": "fixed",
    }
    data = yaml.safe_load(target.read_text(encoding="utf-8"))["en"]
    assert data["greeting"] == "Привет, %{name}!"  # only the requested keys were retranslated
    assert data["inbox"]["messages"]["one"] == "%{count} сообщение"
    assert all("%{count}" in data["inbox"]["messages"][f] for f in ("few", "many"))
    assert [len(texts) for texts, _ in sent] == [2]
