import os

from algebras.config import Config
from algebras.services.file_scanner import FileScanner


def write_file(path: str, content: str = "test"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_scanner_finds_xlf_with_source_files_mapping(tmp_path):
    root = tmp_path
    translations_dir = os.path.join(root, "examples/xliff-app/translations")
    src_file = os.path.join(translations_dir, "messages.en.xlf")
    write_file(src_file, """<?xml version=\"1.0\"?><xliff></xliff>""")

    cfg_path = os.path.join(root, ".algebras.config")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(
            """
languages:
  - en
  - fr
source_files:
  "{src}":
    destination_path: "{dir}/messages.%algebras_locale_code%.xlf"
""".format(src=src_file.replace("\\", "/"), dir=translations_dir.replace("\\", "/"))
        )

    config = Config(cfg_path)
    scanner = FileScanner(config=config)
    files_by_language = scanner.group_files_by_language()

    assert src_file in files_by_language.get("en", [])


def test_scanner_glob_patterns_pick_up_xlf(tmp_path, monkeypatch):
    root = tmp_path
    translations_dir = os.path.join(root, "translations")
    src_file = os.path.join(translations_dir, "messages.en.xlf")
    write_file(src_file, """<?xml version=\"1.0\"?><xliff></xliff>""")

    cfg_path = os.path.join(root, ".algebras.config")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(
            """
languages: ["en", "fr"]
path_rules:
  - "translations/*.xlf"
  - "**/*.xlf"
"""
        )

    # Change to the test directory so glob searches from there
    monkeypatch.chdir(root)
    
    config = Config(cfg_path)
    scanner = FileScanner(config=config)
    found = scanner.find_localization_files()

    # After chdir, paths are relative to root, so normalize both
    expected_rel = os.path.relpath(src_file, root)
    found_normalized = [os.path.normpath(p) for p in found]
    assert os.path.normpath(expected_rel) in found_normalized



