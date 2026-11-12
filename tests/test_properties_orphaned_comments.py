"""
.properties new target: a key left out (untranslated) takes the comment directly above it along,
as in Android strings.xml and .strings files; section comments and the rest of the layout stay.
"""

from algebras.utils.properties_handler import read_properties_file, write_properties_from_template

SOURCE = (
    "# Section: account\n"
    "\n"
    "# Shown on the login button\n"
    "login=Sign in\n"
    "# Shown when the password is wrong\n"
    "! (second comment line)\n"
    "wrong_password=Wrong \\\n"
    "    password\n"
    "logout=Sign out\n"
    "# Footer text\n"
    "footer=Bye"
)


def test_left_out_key_drops_its_comment(tmp_path):
    source = tmp_path / "messages.properties"
    source.write_text(SOURCE, encoding="utf-8")
    target = tmp_path / "messages_de.properties"
    write_properties_from_template(str(target), str(source), {"login": "Anmelden", "logout": "Abmelden"})

    assert target.read_text(encoding="utf-8") == (
        "# Section: account\n"
        "\n"
        "# Shown on the login button\n"
        "login=Anmelden\n"
        "logout=Abmelden"
    )
    assert read_properties_file(str(target)) == {"login": "Anmelden", "logout": "Abmelden"}


def test_all_keys_kept_is_the_source_layout(tmp_path):
    source = tmp_path / "messages.properties"
    source.write_text(SOURCE, encoding="utf-8")
    target = tmp_path / "messages_de.properties"
    values = read_properties_file(str(source))
    write_properties_from_template(str(target), str(source), values)
    assert target.read_text(encoding="utf-8") == SOURCE
