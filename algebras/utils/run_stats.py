"""
Outcome of a `translate` / `update` run: which files succeeded or failed, how many keys were
left out, and the exit code that follows from it.

Exit codes:
    0  everything was translated
    1  errors: a file failed, or the run could not proceed
    2  completed, but some keys were left out (placeholders rejected or API batches failed);
       they are retried on the next run
"""

import traceback
from contextlib import contextmanager
from typing import Any, List, Tuple

import click
from colorama import Fore

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_KEYS_LEFT_OUT = 2


def _counter(translator: Any, name: str) -> int:
    value = getattr(translator, name, 0)
    return value if isinstance(value, int) else 0


class RunStats:
    """Collects per-file results of one run."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.files_ok = 0
        self.files_failed: List[Tuple[str, str]] = []
        self.keys_left_out = 0
        # Set when the run as a whole could not proceed (config, scanning, ...).
        self.fatal = False

    def fail(self, label: str, error: Any) -> None:
        reason = str(error) or type(error).__name__
        self.files_failed.append((label, reason))
        click.echo(f"  {Fore.RED}✗ {label}: {reason}{Fore.RESET}")
        if self.verbose and isinstance(error, BaseException):
            click.echo("".join(traceback.format_exception(type(error), error, error.__traceback__)))

    @contextmanager
    def file(self, label: str, translator: Any = None):
        """
        Guard one file: an exception is reported (file plus reason, traceback only with
        --verbose) and counted as a failed file instead of stopping the run. Keys the translator
        left out while the block ran are counted; a file whose every key was left out failed.
        """
        sent_before = _counter(translator, "keys_sent")
        left_before = _counter(translator, "keys_left_out")
        try:
            yield
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the run
            self.fail(label, e)
            return
        sent = _counter(translator, "keys_sent") - sent_before
        left = _counter(translator, "keys_left_out") - left_before
        self.keys_left_out += left
        if sent > 0 and left >= sent:
            self.fail(label, f"no key could be translated ({left} left out)")
        else:
            self.files_ok += 1

    def exit_code(self) -> int:
        if self.fatal or self.files_failed:
            return EXIT_ERROR
        if self.keys_left_out:
            return EXIT_KEYS_LEFT_OUT
        return EXIT_OK

    def summary_line(self) -> str:
        return (
            f"{self.files_ok} files OK, {len(self.files_failed)} files failed, "
            f"{self.keys_left_out} keys left out"
        )

    def print_summary(self) -> int:
        """Print the summary line (unless no file was processed) and return the exit code."""
        code = self.exit_code()
        if not self.files_ok and not self.files_failed and not self.keys_left_out:
            return code
        color = {EXIT_OK: Fore.GREEN, EXIT_KEYS_LEFT_OUT: Fore.YELLOW}.get(code, Fore.RED)
        click.echo(f"\n{color}{self.summary_line()}{Fore.RESET}")
        if code == EXIT_KEYS_LEFT_OUT:
            click.echo(f"{Fore.YELLOW}Keys left out are retried on the next run.{Fore.RESET}")
        return code
