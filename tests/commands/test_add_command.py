"""
Tests for the add command
"""

from unittest.mock import patch, MagicMock

import pytest
import click
from click.testing import CliRunner

from algebras.commands import add_command
from algebras.config import Config


class TestAddCommand:
    """Tests for the add command"""

    def test_execute_invalid_language(self):
        """Test execute with invalid language code"""
        # Patch click.echo
        with patch("algebras.commands.add_command.click.echo") as mock_echo:
            # Call execute with invalid language
            add_command.execute("x")
            
            # Verify output message
            mock_echo.assert_called_once_with(f"{click.style('Invalid language code. Please use a valid ISO language code (e.g., \'fr\', \'es\').', fg='red')}")

    def test_execute_no_config(self):
        """Test execute with no config file"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = False
        
        # Patch Config and click.echo
        with patch("algebras.commands.add_command.Config", return_value=mock_config), \
             patch("algebras.commands.add_command.click.echo") as mock_echo:
            
            # Call execute
            add_command.execute("fr")
            
            # Verify Config was used
            assert mock_config.exists.called
            
            # Verify output message
            mock_echo.assert_called_once_with(f"{click.style('No Algebras configuration found. Run \'algebras init\' first.', fg='red')}")

    def test_execute_existing_language(self):
        """Test execute with already existing language"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.check_deprecated_format.return_value = False
        
        # Patch Config and click.echo
        with patch("algebras.commands.add_command.Config", return_value=mock_config), \
             patch("algebras.commands.add_command.click.echo") as mock_echo:
            
            # Call execute
            add_command.execute("fr")
            
            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert not mock_config.add_language.called
            
            # Verify output message
            mock_echo.assert_called_once_with(f"{click.style('Language \'fr\' is already configured.', fg='yellow')}")

    def test_execute_add_new_language(self):
        """Test execute with new language"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en"]
        mock_config.check_deprecated_format.return_value = False
        
        # Patch Config and click.echo
        with patch("algebras.commands.add_command.Config", return_value=mock_config), \
             patch("algebras.commands.add_command.click.echo") as mock_echo:
            
            # Call execute
            add_command.execute("fr")
            
            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_config.add_language.called
            mock_config.add_language.assert_called_once_with("fr")
            
            # Verify output messages
            mock_echo.assert_any_call(f"{click.style('Adding language \'fr\' to your project...', fg='green')}")
            mock_echo.assert_any_call(f"{click.style('✓ Language \'fr\' has been added to your project.', fg='green')}")

    def test_execute_integration(self):
        """Test execute with the CLI runner"""
        # Use a real CLI runner to test the click command
        runner = CliRunner()
        
        # Patch the execute function in add_command
        with patch("algebras.commands.add_command.execute") as mock_execute:
            from algebras.cli import add
            
            # Run the command
            result = runner.invoke(add, ["fr"])
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments
            mock_execute.assert_called_once_with(["fr"], None)
            
            # Test with missing argument
            result = runner.invoke(add)
            
            # Command should fail because language is required
            assert result.exit_code != 0

    def test_execute_integration_multiple_languages(self):
        """The CLI accepts several languages in one command"""
        runner = CliRunner()

        with patch("algebras.commands.add_command.execute") as mock_execute:
            from algebras.cli import add

            result = runner.invoke(add, ["es", "fr", "de"])

            assert result.exit_code == 0, result.output
            mock_execute.assert_called_once_with(["es", "fr", "de"], None)

    def test_execute_add_multiple_languages(self):
        """Each new language is added; already-configured and duplicate codes are skipped"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.check_deprecated_format.return_value = False

        with patch("algebras.commands.add_command.Config", return_value=mock_config), \
             patch("algebras.commands.add_command.click.echo") as mock_echo:

            add_command.execute(["ES", "fr", "de", "es"])

            assert [c.args[0] for c in mock_config.add_language.call_args_list] == ["es", "de"]
            mock_echo.assert_any_call(f"{click.style('Language \'fr\' is already configured.', fg='yellow')}")
            mock_echo.assert_any_call(f"{click.style('✓ Language \'es\' has been added to your project.', fg='green')}")
            mock_echo.assert_any_call(f"{click.style('✓ Language \'de\' has been added to your project.', fg='green')}")

    def test_execute_multiple_with_invalid_adds_nothing(self):
        """An invalid code in the list aborts before the config is touched"""
        with patch("algebras.commands.add_command.Config") as mock_config_class, \
             patch("algebras.commands.add_command.click.echo"):

            add_command.execute(["es", "x", "de"])

            assert not mock_config_class.called
