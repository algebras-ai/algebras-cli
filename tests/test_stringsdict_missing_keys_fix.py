"""
Tests for the .stringsdict "missing keys not written" bug fix.

Bug report: translating a .stringsdict file reported success ("Updated 54
keys in .../az.lproj/Localizable.stringsdict", "STRINGSDICT format does not
support in-place updates yet, regenerating from scratch") but the target
file on disk never actually changed.

Root cause: StringsDictHandler.write() rebuilt the target file by calling
update_translatable_strings(target_raw_content, translations) using only the
*target* file's existing (incomplete) raw structure as a base. That function
only overwrites values for keys that already exist in the structure it is
given - it never adds brand new top-level entries. So any translation for a
key that didn't already exist in the target file (i.e. every "missing key"
being translated for the first time) was silently dropped, and the
regenerated file came out identical to the original.

Fix: pass source_raw_content through (like the XLIFF handler already does)
and use it as a structural template - update_translatable_strings now copies
over any entry that exists in the source but not yet in the target before
applying translations, so newly-translated keys actually get written.

The fixture data below is a self-contained stand-in for the real
Localizable.stringsdict shape the bug was reported against (61 source keys,
54 missing from the target, `az` target language) - it doesn't depend on
any external file.
"""

import copy
import os
import tempfile

import pytest

from algebras.utils.ios_stringsdict_handler import (
    extract_translatable_strings,
    read_ios_stringsdict_file,
    update_translatable_strings,
    write_ios_stringsdict_file,
)
from algebras.utils.file_format_handlers.stringsdict_handler import StringsDictHandler


_STRINGS_FIXTURE_KEYS = [
    ("Auth.eula", "user agreement"),
    ("Auth.privacy_policy", "privacy policy"),
    ("Auth.sign_in_with", "Sign in with %1$s"),
    ("Auth.user_agreement", "By registering, I agree to the terms"),
    ("Auth.welcome_disclaimer", "Hi! Join us for free to get started"),
    ("Chat.comment_hint", "Your comment..."),
    ("Chat.empty_placeholder", "While there are no messages"),
    ("Chat.publish", "Send"),
    ("Chat.published", "Your comment has been published"),
    ("Chat.publishing", "Publishing your comment"),
    ("Chat.updated", "Your comment has been updated"),
    ("Chat.updating", "Updating your comment"),
    ("Chat.write_comment", "Write a comment..."),
    ("Checklist.dropdown_hint", "Choose an option"),
    ("Checklist.dropdown_title", "Your answer"),
    ("Checklist.multiple_answers", "You can choose up to %1$d options"),
    ("Checklist.single_answer", "You can choose 1 option"),
    ("Common.and", "and"),
    ("Common.cancel", "Cancel"),
    ("Common.confirm_delete", "Yes, delete"),
    ("Common.congrats", "Congratulate"),
    ("Common.continue", "Continue"),
    ("Common.course_completed", "Course is over"),
    ("Common.delete", "Delete"),
    ("Common.deleting", "Deleting"),
    ("Common.dislike", "Dislike"),
    ("Common.done", "Done"),
    ("Common.edit", "Edit"),
    ("Common.error", "Error"),
    ("Common.error_title", "Something went wrong, please try again later"),
    ("Common.file", "File"),
    ("Common.icon", "icon"),
    ("Common.like", "Like"),
    ("Common.loading", "Loading"),
    ("Common.media", "media"),
    ("Common.more", "more"),
    ("Common.not_now", "Not now"),
    ("Common.ok", "OK"),
    ("Common.photo", "Photo"),
    ("Common.picker_select", "Select"),
    ("Common.read_all", "Read all"),
    ("Common.save", "Save"),
    ("Common.send", "Send"),
    ("Common.task", "Task"),
    ("Common.try_again", "Try again"),
    ("Common.untitled_file", "untitled"),
    ("Common.update", "Update"),
    ("Common.video", "Video"),
    ("Course.all_information", "All course information"),
    ("Course.all_information_title", "About course"),
    ("Course.applicant_start", "Start"),
    ("Course.buy_description", "Pay once, get unlimited access"),
    ("Course.buy_for", "Buy here for %1$s"),
    ("Course.chapter", "Chapter %1$d"),
    ("Course.dates_current", "Finishes on %1$s"),
    ("Course.dates_future", "Runs from %1$s to %2$s"),
    ("Course.dates_past", "Took place from %1$s to %2$s"),
    ("Course.day", "Day %1$d"),
    ("Course.empty_days_description", "The course schedule is coming soon"),
    ("Course.excluded", "You were excluded"),
    ("Course.in_progress", "%1$s out of %2$s"),
]


def _load_strings_keys(limit=None):
    """Return the self-contained fixture key/value pairs."""
    return _STRINGS_FIXTURE_KEYS[:limit] if limit else list(_STRINGS_FIXTURE_KEYS)


def _build_stringsdict_source(keys):
    """
    Build a .stringsdict raw structure (source/en) with one pluralized entry
    per key, using the .strings values as the "other" plural form text.
    """
    content = {}
    for key, value in keys:
        format_key = f"{key}_count"
        content[key] = {
            "NSStringLocalizedFormatKey": f"%#@{format_key}@",
            format_key: {
                "NSStringFormatSpecTypeKey": "NSStringPluralRuleType",
                "NSStringFormatValueTypeKey": "d",
                "zero": f"No {value}",
                "one": f"One {value}",
                "other": f"%d {value}",
            },
        }
    return content


class TestStringsDictMissingKeysFix:
    @pytest.fixture
    def source_and_target(self):
        """
        61 keys total in source (mirrors the real Localizable.stringsdict
        shape); target already has translations for 7 of them and is
        missing the other 54 - exactly like the bug report.
        """
        keys = _load_strings_keys(limit=61)
        assert len(keys) == 61

        source_raw = _build_stringsdict_source(keys)

        existing_keys = keys[:7]
        missing_keys = keys[7:]
        assert len(missing_keys) == 54

        target_raw = {}
        for key, value in existing_keys:
            format_key = f"{key}_count"
            target_raw[key] = {
                "NSStringLocalizedFormatKey": f"%#@{format_key}@",
                format_key: {
                    "NSStringFormatSpecTypeKey": "NSStringPluralRuleType",
                    "NSStringFormatValueTypeKey": "d",
                    "zero": f"[az] No {value}",
                    "one": f"[az] One {value}",
                    "other": f"[az] %d {value}",
                },
            }

        return source_raw, target_raw, existing_keys, missing_keys

    def test_bug_reproduction_without_source_content_drops_missing_keys(self, source_and_target):
        """
        Regression guard: demonstrates the original bug. Without a source
        structure to use as a template, update_translatable_strings cannot
        invent new entries, so translations for keys absent from the target
        are silently discarded and the output equals the input.
        """
        source_raw, target_raw, existing_keys, missing_keys = source_and_target

        translations = {}
        for key, _ in existing_keys + missing_keys:
            format_key = f"{key}_count"
            translations[f"{key}.{format_key}.zero"] = f"[az] No X"
            translations[f"{key}.{format_key}.one"] = f"[az] One X"
            translations[f"{key}.{format_key}.other"] = f"[az] %d X"

        # Old call signature: no source_content template available.
        result = update_translatable_strings(target_raw, translations)

        # Still missing - this is the reported bug.
        for key, _ in missing_keys:
            assert key not in result
        assert result == target_raw or set(result.keys()) == set(target_raw.keys())

    def test_missing_keys_are_added_using_source_as_template(self, source_and_target):
        """The fix: missing keys get pulled in from source_content and translated."""
        source_raw, target_raw, existing_keys, missing_keys = source_and_target

        translations = {}
        for key, _ in existing_keys + missing_keys:
            format_key = f"{key}_count"
            translations[f"{key}.{format_key}.zero"] = f"[az] No X ({key})"
            translations[f"{key}.{format_key}.one"] = f"[az] One X ({key})"
            translations[f"{key}.{format_key}.other"] = f"[az] %d X ({key})"

        result = update_translatable_strings(target_raw, translations, source_raw)

        # All 61 keys now present, not just the 7 that pre-existed.
        assert set(result.keys()) == set(source_raw.keys())

        for key, _ in missing_keys:
            format_key = f"{key}_count"
            plural = result[key][format_key]
            assert plural["other"] == translations[f"{key}.{format_key}.other"]
            assert plural["zero"] == translations[f"{key}.{format_key}.zero"]
            assert plural["one"] == translations[f"{key}.{format_key}.one"]

        for key, _ in existing_keys:
            format_key = f"{key}_count"
            plural = result[key][format_key]
            assert plural["other"] == translations[f"{key}.{format_key}.other"]

    def test_write_ios_stringsdict_via_handler_end_to_end(self, source_and_target):
        """
        End-to-end: drive it through StringsDictHandler.write() exactly like
        translate_command._write_translated_content() does for the
        STRINGSDICT "regenerate from scratch" path, and confirm the file on
        disk actually changes and contains all 54 previously-missing keys.
        """
        source_raw, target_raw, existing_keys, missing_keys = source_and_target
        all_keys = existing_keys + missing_keys

        translations = {}
        for key, _ in all_keys:
            format_key = f"{key}_count"
            translations[f"{key}.{format_key}.zero"] = f"[az] No X ({key})"
            translations[f"{key}.{format_key}.one"] = f"[az] One X ({key})"
            translations[f"{key}.{format_key}.other"] = f"[az] %d X ({key})"

        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = os.path.join(tmpdir, "Localizable.stringsdict")
            write_ios_stringsdict_file(target_file, target_raw)
            before_mtime_content = open(target_file, encoding="utf-8").read()

            handler = StringsDictHandler()
            handler.write(
                target_file,
                translations,
                raw_content=copy.deepcopy(target_raw),
                source_raw_content=source_raw,
            )

            after_content = open(target_file, encoding="utf-8").read()
            assert after_content != before_mtime_content, (
                "File on disk did not change - this is the reported bug"
            )

            written_raw = read_ios_stringsdict_file(target_file)
            written_flat = extract_translatable_strings(written_raw)

            assert len(written_raw) == 61
            for key, _ in missing_keys:
                format_key = f"{key}_count"
                assert written_flat[f"{key}.{format_key}.other"] == translations[f"{key}.{format_key}.other"]

    def test_write_from_scratch_with_no_existing_target_file(self, source_and_target):
        """
        When the target .stringsdict doesn't exist on disk at all yet,
        write() should still succeed by using source_raw_content as the
        base structure, rather than raising ValueError.
        """
        source_raw, _target_raw, existing_keys, missing_keys = source_and_target
        all_keys = existing_keys + missing_keys

        translations = {}
        for key, _ in all_keys:
            format_key = f"{key}_count"
            translations[f"{key}.{format_key}.other"] = f"[az] %d X ({key})"

        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = os.path.join(tmpdir, "Localizable.stringsdict")
            assert not os.path.exists(target_file)

            handler = StringsDictHandler()
            handler.write(
                target_file,
                translations,
                raw_content=None,
                source_raw_content=source_raw,
            )

            assert os.path.exists(target_file)
            written_raw = read_ios_stringsdict_file(target_file)
            assert set(written_raw.keys()) == set(source_raw.keys())

    def test_write_without_raw_or_source_content_still_raises(self):
        """Existing safety check is preserved when there's truly nothing to build from."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = os.path.join(tmpdir, "Localizable.stringsdict")
            handler = StringsDictHandler()
            with pytest.raises(ValueError):
                handler.write(target_file, {}, raw_content=None, source_raw_content=None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
