"""
i18next JSON plurals get the CLDR forms the target language needs (en one/other -> ru
one/few/many/other) on every translate path, placed next to their group; status, missing-key
detection and 'algebras placeholders' count and check those forms. JSON that is not i18next is
never expanded. Android <plurals> missing a form is reported as `missing_form` and refilled by
--retranslate.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, translate_command
from algebras.commands.status_command import _expected_key_count, count_current_and_outdated_keys
from algebras.config import Config
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import android_xml as android_format
from algebras.services.placeholders.formats import json_format
from algebras.utils.android_xml_handler import read_android_xml_file
from algebras.utils.lang_validator import validate_language_files

RU_FORMS = ["one", "few", "many", "other"]

I18NEXT_EN = {
    "greeting": "Hello, {{name}}!",
    "cart": {
        "title": "Your cart",
        "item_one": "One item",
        "item_other": "{{count}} items",
        "total": "Total: {{value}}",
    },
    "apple_one": "{{count}} apple",
    "apple_other": "{{count}} apples",
}

# FormatJS / plain JSON whose keys happen to end in _one / _other: no {{…}} anywhere.
PLAIN_EN = {
    "welcome": "Welcome, {name}!",
    "step_one": "First step",
    "step_other": "Other steps",
}


@pytest.fixture(autouse=True)
def real_fix_writers():
    # Other tests may replace writers with recording ones; use the real ones here.
    register_fix_writer([".json"], json_format.write_fixes)
    register_fix_writer([".xml"], android_format.write_fixes)
    yield


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)


def _fake_client(sent):
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        sent.append((list(texts), list(kwargs.get("contexts") or [None] * len(texts))))
        return [f"ru {t}" for t in texts]

    client.translate_batch.side_effect = translate_batch
    client.translate.side_effect = lambda text, *a, **k: f"ru {text}"
    return client


def _run(sent, fn, **kwargs):
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        return fn(**kwargs)


def _write_json(path, data, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def json_project(tmp_path, monkeypatch):
    sources = {
        "i18next": _write_json(tmp_path / "locales" / "en" / "i18next.json", I18NEXT_EN),
        "plain": _write_json(tmp_path / "locales" / "en" / "plain.json", PLAIN_EN),
    }
    source_files = {
        f"locales/en/{name}.json": {"destination_path": f"locales/%algebras_locale_code%/{name}.json"}
        for name in sources
    }
    (tmp_path / ".algebras.config").write_text(
        json.dumps({"languages": ["en", "ru"], "source_files": source_files, "api": {"provider": "algebras-ai"}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return {
        "sources": sources,
        "targets": {name: tmp_path / "locales" / "ru" / f"{name}.json" for name in sources},
    }


def _plural_keys(level, base):
    return [k for k in level if k.startswith(base + "_")]


def _sent_pairs(sent):
    return [(t, c) for texts, contexts in sent for t, c in zip(texts, contexts)]


# ---------------------------------------------------------------------------
# Translate paths
# ---------------------------------------------------------------------------


def test_full_translate_writes_every_ru_form_in_cldr_order(json_project):
    sent = []
    _run(sent, translate_command.execute, language="ru", force="__all__")

    data = json.loads(json_project["targets"]["i18next"].read_text(encoding="utf-8"))
    # New forms sit next to their group, in CLDR order, and the rest keeps the source order.
    assert list(data["cart"]) == ["title", "item_one", "item_few", "item_many", "item_other", "total"]
    assert list(data) == ["greeting", "cart", "apple_one", "apple_few", "apple_many", "apple_other"]
    for level, base in ((data["cart"], "item"), (data, "apple")):
        assert _plural_keys(level, base) == [f"{base}_{f}" for f in RU_FORMS]
        for form in RU_FORMS:
            assert "{{count}}" in level[f"{base}_{form}"], (base, form, level[f"{base}_{form}"])
    # Each generated form came with a note on the counts it covers.
    notes = [c for _, c in _sent_pairs(sent) if c and "i18next plural form 'few' for Russian" in c]
    assert len(notes) == 2 and all("2, 3, 4" in n for n in notes)


def test_missing_only_adds_few_and_many_to_an_existing_target(json_project):
    _write_json(json_project["targets"]["plain"], {"welcome": "Привет, {name}!", "step_one": "Шаг", "step_other": "Шаги"})
    target = _write_json(
        json_project["targets"]["i18next"],
        {
            "greeting": "Привет, {{name}}!",
            "cart": {
                "title": "Ваша корзина",
                "item_one": "{{count}} товар",
                "item_other": "{{count}} товара",
                "total": "Итого: {{value}}",
            },
            "apple_one": "{{count}} яблоко",
            "apple_other": "{{count}} яблока",
        },
        indent=4,
    )
    before = target.read_text(encoding="utf-8")
    ok, missing = validate_language_files(
        str(json_project["sources"]["i18next"]), str(target), target_language="ru"
    )
    assert not ok and missing == {"cart.item_few", "cart.item_many", "apple_few", "apple_many"}

    sent = []
    _run(sent, translate_command.execute, language="ru", only_missing=True)

    text = target.read_text(encoding="utf-8")
    data = json.loads(text)
    assert list(data["cart"]) == ["title", "item_one", "item_few", "item_many", "item_other", "total"]
    assert _plural_keys(data, "apple") == [f"apple_{f}" for f in RU_FORMS]
    # Existing values stay as they were; only the new forms were sent, from the _other text.
    assert data["cart"]["item_one"] == "{{count}} товар" and data["greeting"] == "Привет, {{name}}!"
    assert all("{{count}}" in data["cart"][f"item_{f}"] for f in ("few", "many"))
    assert sorted(t for texts, _ in sent for t in texts) == ["⟦0⟧ apples"] * 2 + ["⟦0⟧ items"] * 2
    assert "    " in text and before.splitlines()[1] == text.splitlines()[1]  # 4-space layout kept
    assert validate_language_files(str(json_project["sources"]["i18next"]), str(target), target_language="ru") == (
        True,
        set(),
    )


def test_outdated_file_path_adds_the_forms_as_missing_keys(json_project):
    target = _write_json(
        json_project["targets"]["i18next"],
        {"cart": {"item_one": "{{count}} товар", "item_other": "{{count}} товара"}},
    )
    sent = []
    _run(
        sent,
        translate_command.execute,
        language="ru",
        only_missing=True,
        outdated_files=[(str(target), str(json_project["sources"]["i18next"]))],
    )
    data = json.loads(target.read_text(encoding="utf-8"))
    assert list(data["cart"]) == ["title", "item_one", "item_few", "item_many", "item_other", "total"]
    assert data["cart"]["item_one"] == "{{count}} товар"  # existing forms are not outdated
    assert _plural_keys(data, "apple") == [f"apple_{f}" for f in RU_FORMS]
    assert all("{{count}}" in data["cart"][f"item_{f}"] for f in ("few", "many"))


def test_status_counts_generated_forms_and_never_reports_them_outdated(json_project):
    sent = []
    _run(sent, translate_command.execute, language="ru", force="__all__")
    config = Config()
    config.load()
    source = str(json_project["sources"]["i18next"])
    target = str(json_project["targets"]["i18next"])

    # 7 source strings + item_few/many + apple_few/many for Russian.
    assert _expected_key_count(source, "ru", {source: 7}, config) == 11
    assert _expected_key_count(source, "de", {source: 7}, config) == 7
    assert count_current_and_outdated_keys(source, target, None, "ru", config) == (11, 0)


def test_non_i18next_json_is_never_expanded(json_project):
    sent = []
    _run(sent, translate_command.execute, language="ru", force="__all__")

    source = str(json_project["sources"]["plain"])
    target = json_project["targets"]["plain"]
    data = json.loads(target.read_text(encoding="utf-8"))
    assert list(data) == list(PLAIN_EN)
    config = Config()
    config.load()
    assert _expected_key_count(source, "ru", {source: 3}, config) == 3
    assert validate_language_files(source, str(target), target_language="ru") == (True, set())
    assert count_current_and_outdated_keys(source, str(target), None, "ru", config) == (3, 0)
    assert json_format.check_file(source, str(target), "en", "ru") == []

    # A missing-only run has nothing to add either.
    before = target.read_text(encoding="utf-8")
    _run(sent, translate_command.execute, language="ru", only_missing=True)
    assert target.read_text(encoding="utf-8") == before


def test_placeholders_reports_missing_i18next_forms_and_retranslate_fills_them(json_project, capsys):
    target = _write_json(
        json_project["targets"]["i18next"],
        {
            "greeting": "Привет, {{name}}!",
            "cart": {"title": "Корзина", "item_one": "{{count}} товар", "item_other": "{{count}} товара",
                     "total": "Итого: {{value}}"},
            "apple_one": "{{count}} яблоко",
            "apple_few": "{{count}} яблока",
            "apple_many": "{{count}} яблок",
            "apple_other": "{{count}} яблока",
        },
    )
    _write_json(json_project["targets"]["plain"], {"welcome": "Привет, {name}!", "step_one": "Шаг", "step_other": "Шаги"})

    capsys.readouterr()
    code = placeholders_command.execute(output_format="json")
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert {(i["key"], i["problems"][0]["code"]) for i in report["issues"]} == {
        ("cart.item_few", "missing_form"),
        ("cart.item_many", "missing_form"),
    }

    sent = []
    capsys.readouterr()
    code = _run(sent, placeholders_command.execute, output_format="json", fix=True, retranslate=True)
    out = capsys.readouterr().out
    report = json.loads(out[out.index("\n{\n") + 1 :])
    assert code == 0
    assert {i["key"]: i["status"] for i in report["issues"]} == {"cart.item_few": "fixed", "cart.item_many": "fixed"}
    data = json.loads(target.read_text(encoding="utf-8"))
    assert list(data["cart"]) == ["title", "item_one", "item_few", "item_many", "item_other", "total"]
    assert data["cart"]["item_one"] == "{{count}} товар"


# ---------------------------------------------------------------------------
# Android <plurals>: missing_form
# ---------------------------------------------------------------------------

ANDROID_EN = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="hello">Hello %1$s</string>
    <plurals name="points">
        <item quantity="one">%1$d point</item>
        <item quantity="other">%1$d points</item>
    </plurals>
</resources>
"""

ANDROID_RU = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="hello">Привет %1$s</string>
    <plurals name="points">
        <item quantity="one">%1$d очко</item>
        <item quantity="many">%1$d очков</item>
        <item quantity="other">%1$d очка</item>
    </plurals>
</resources>
"""


@pytest.fixture
def android_project(tmp_path, monkeypatch):
    (tmp_path / "res" / "values").mkdir(parents=True)
    (tmp_path / "res" / "values-ru").mkdir(parents=True)
    source = tmp_path / "res" / "values" / "strings.xml"
    target = tmp_path / "res" / "values-ru" / "strings.xml"
    source.write_text(ANDROID_EN, encoding="utf-8")
    target.write_text(ANDROID_RU, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "ru"],
                "source_files": {
                    "res/values/strings.xml": {"destination_path": "res/values-%algebras_locale_code%/strings.xml"}
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return source, target


def test_android_missing_plural_form_is_reported(android_project):
    source, target = android_project
    findings = android_format.check_file(str(source), str(target), "en", "ru")
    assert [(f.key, f.path, [p.code for p in f.problems], f.fixed) for f in findings] == [
        ("points.__plurals__.few", ("points.__plurals__", "few"), ["missing_form"], None)
    ]
    assert findings[0].source == "%1$d points"
    assert "Plural form 'few' is missing (ru needs one, few, many, other)" == findings[0].problems[0].message
    # A plural group the target has not translated at all is left to 'status'.
    target.write_text('<resources><string name="hello">Привет %1$s</string></resources>', encoding="utf-8")
    assert android_format.check_file(str(source), str(target), "en", "ru") == []


def test_android_retranslate_fills_the_missing_form(android_project, capsys):
    _, target = android_project
    sent = []
    capsys.readouterr()
    code = _run(sent, placeholders_command.execute, output_format="json", fix=True, retranslate=True)
    out = capsys.readouterr().out
    report = json.loads(out[out.index("\n{\n") + 1 :])
    assert code == 0
    assert {i["key"]: (i["problems"][0]["code"], i["status"]) for i in report["issues"]} == {
        "points.__plurals__.few": ("missing_form", "fixed")
    }
    data = read_android_xml_file(str(target))
    assert list(data["points.__plurals__"]) == RU_FORMS
    assert "%1$d" in data["points.__plurals__"]["few"]
    assert data["hello"] == "Привет %1$s"  # only the plural group was retranslated
