"""
Tests for glossary list and download commands.
"""

import json
import sys
import types
from unittest.mock import MagicMock, mock_open, patch

from click.testing import CliRunner

sys.modules.setdefault("pyicumessageformat", types.SimpleNamespace(Parser=MagicMock()))

from algebras.cli import glossary
from algebras.commands import glossary_download_command, glossary_list_command
from algebras.config import Config


class TestGlossaryListCommand:
    def test_execute_allows_no_config(self):
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = False
        mock_service = MagicMock()
        mock_service.list_glossaries.return_value = {"items": []}

        with patch("algebras.commands.glossary_list_command.Config", return_value=mock_config), \
             patch("algebras.commands.glossary_list_command.GlossaryService", return_value=mock_service), \
             patch("algebras.commands.glossary_list_command.click.echo") as mock_echo:
            glossary_list_command.execute()

            assert mock_config.exists.called
            assert not mock_config.load.called
            mock_service.list_glossaries.assert_called_once_with(limit=100, page=1)
            assert "No glossaries found" in mock_echo.call_args[0][0]

    def test_execute_json_output(self):
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_service = MagicMock()
        mock_service.list_glossaries.return_value = {
            "data": [
                {
                    "id": "g1",
                    "name": "Product",
                    "status": "READY",
                    "createdAt": "2026-01-01T00:00:00.000Z",
                    "updatedAt": "2026-01-02T00:00:00.000Z",
                    "languages": [{"language": "en"}, {"language": "es"}],
                    "terms": [{"id": "t1"}, {"id": "t2"}],
                }
            ],
            "pagination": {"page": 2, "limit": 50, "total": 1, "totalPages": 1},
        }

        with patch("algebras.commands.glossary_list_command.Config", return_value=mock_config), \
             patch("algebras.commands.glossary_list_command.GlossaryService", return_value=mock_service), \
             patch("algebras.commands.glossary_list_command.click.echo") as mock_echo:
            glossary_list_command.execute(output_format="json", limit=50, page=2)

            payload = json.loads(mock_echo.call_args[0][0])
            assert payload["items"][0]["id"] == "g1"
            assert payload["items"][0]["name"] == "Product"
            assert payload["items"][0]["languages"] == ["en", "es"]
            assert payload["items"][0]["termCount"] == 2
            assert "terms" not in payload["items"][0]
            assert payload["pagination"]["page"] == 2
            mock_service.list_glossaries.assert_called_once_with(limit=50, page=2)


class TestGlossaryDownloadCommand:
    def test_execute_downloads_glossary_and_terms(self):
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = False
        mock_service = MagicMock()
        mock_service.get_glossary.return_value = {"id": "g1", "name": "Product"}
        mock_service.list_terms.side_effect = [
            {"items": [{"id": "t1"}], "pagination": {"page": 1, "totalPages": 2}},
            {"items": [{"id": "t2"}], "pagination": {"page": 2, "totalPages": 2}},
        ]

        with patch("algebras.commands.glossary_download_command.Config", return_value=mock_config), \
             patch("algebras.commands.glossary_download_command.GlossaryService", return_value=mock_service), \
             patch("algebras.commands.glossary_download_command.os.makedirs"), \
             patch("builtins.open", mock_open()) as opened, \
             patch("algebras.commands.glossary_download_command.click.echo"):
            glossary_download_command.execute("g1", ".algebras/glossaries/g1.json")

            assert not mock_config.load.called
            assert mock_service.list_terms.call_args_list[0].kwargs == {"limit": 100, "page": 1}
            assert mock_service.list_terms.call_args_list[1].kwargs == {"limit": 100, "page": 2}
            opened.assert_called_once_with(".algebras/glossaries/g1.json", "w", encoding="utf-8")
            handle = opened()
            written = "".join(call.args[0] for call in handle.write.call_args_list)
            assert '"glossary"' in written
            assert '"terms"' in written


class TestGlossaryCLI:
    def test_glossary_list_cli(self):
        runner = CliRunner()
        with patch("algebras.commands.glossary_list_command.execute") as mock_execute:
            result = runner.invoke(glossary, ["list", "--format", "json"])

            assert result.exit_code == 0
            mock_execute.assert_called_once()
            assert mock_execute.call_args.kwargs["output_format"] == "json"

    def test_glossary_download_cli(self):
        runner = CliRunner()
        with patch("algebras.commands.glossary_download_command.execute") as mock_execute:
            result = runner.invoke(glossary, ["download", "g1", "--output", ".algebras/glossaries/g1.json"])

            assert result.exit_code == 0
            mock_execute.assert_called_once()
            assert mock_execute.call_args.args[:2] == ("g1", ".algebras/glossaries/g1.json")
