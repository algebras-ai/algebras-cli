"""
Tests for the init command
"""

from unittest.mock import patch, MagicMock

import pytest
import click
from click.testing import CliRunner

from algebras.commands import init_command
from algebras.config import Config


class TestInitCommand:
    """Tests for the init command"""

    def test_execute_new_config(self):
        """Test execute with no existing config"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = False
        mock_config.config_path = "/path/to/.algebras.config"

        # Patch Config and click.echo
        with patch("algebras.commands.init_command.Config", return_value=mock_config), \
             patch("algebras.commands.init_command.click.echo") as mock_echo:
            
            # Call execute
            init_command.execute()
            
            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.create_default.called
            
            # Verify output messages
            mock_echo.assert_any_call(f"{click.style('Initializing Algebras project...', fg='green')}")
            mock_echo.assert_any_call(f"{click.style('✓ Created configuration file: ', fg='green')}{mock_config.config_path}")

    def test_execute_existing_config_no_force(self):
        """Test execute with existing config and no force option"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        
        # Patch Config and click.echo
        with patch("algebras.commands.init_command.Config", return_value=mock_config), \
             patch("algebras.commands.init_command.click.echo") as mock_echo:
            
            # Call execute
            init_command.execute(force=False)
            
            # Verify Config was used correctly
            assert mock_config.exists.called
            assert not mock_config.create_default.called
            
            # Verify output message
            mock_echo.assert_called_once_with(f"{click.style('Config file already exists. Use --force to overwrite.', fg='yellow')}")

    def test_execute_existing_config_with_force(self):
        """Test execute with existing config and force option"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.config_path = "/path/to/.algebras.config"
        
        # Patch Config and click.echo
        with patch("algebras.commands.init_command.Config", return_value=mock_config), \
             patch("algebras.commands.init_command.click.echo") as mock_echo:
            
            # Call execute
            init_command.execute(force=True)
            
            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.create_default.called
            
            # Verify output messages
            mock_echo.assert_any_call(f"{click.style('Initializing Algebras project...', fg='green')}")
            mock_echo.assert_any_call(f"{click.style('✓ Created configuration file: ', fg='green')}{mock_config.config_path}")

    def test_execute_integration(self):
        """Test execute with the CLI runner"""
        # Use a real CLI runner to test the click command
        runner = CliRunner()
        
        # Patch the execute function in init_command
        with patch("algebras.commands.init_command.execute") as mock_execute:
            from algebras.cli import init
            
            # Run the command
            result = runner.invoke(init)
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments (force=False, verbose=False)
            mock_execute.assert_called_once_with(False, False)
            
            # Test with force option
            result = runner.invoke(init, ["--force"])
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments
            mock_execute.assert_called_with(True, False) 