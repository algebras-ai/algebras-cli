"""
Glossary list command implementation.
"""

import json
from typing import Any, Dict, List

import click
from colorama import Fore

from algebras.config import Config
from algebras.services.glossary_service import GlossaryService


def _extract_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return glossary items from common paginated API response shapes."""
    if isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data.get("glossaries"), list):
        return data["glossaries"]
    if isinstance(data.get("data"), list):
        return data["data"]
    if isinstance(data, list):
        return data
    return []


def _language_codes(languages_raw: List[Any]) -> List[str]:
    """Return language codes from API language objects."""
    languages = []
    for language in languages_raw or []:
        if isinstance(language, str):
            languages.append(language)
        elif isinstance(language, dict):
            code = (
                language.get("code")
                or language.get("language")
                or language.get("languageCode")
                or language.get("id")
            )
            if code:
                languages.append(code)
    return languages


def _term_count(glossary: Dict[str, Any]) -> int:
    """Return term count from common glossary metadata shapes."""
    for key in ("termCount", "termsCount", "terms_count", "_count"):
        value = glossary.get(key)
        if isinstance(value, int):
            return value
        if key == "_count" and isinstance(value, dict) and isinstance(value.get("terms"), int):
            return value["terms"]
    terms = glossary.get("terms")
    return len(terms) if isinstance(terms, list) else 0


def _summarize_glossary(glossary: Dict[str, Any]) -> Dict[str, Any]:
    """Return compact glossary metadata without embedded term content."""
    return {
        "id": glossary.get("id", ""),
        "name": glossary.get("name", "Untitled glossary"),
        "status": glossary.get("status", ""),
        "createdAt": glossary.get("createdAt"),
        "updatedAt": glossary.get("updatedAt"),
        "languages": _language_codes(glossary.get("languages", [])),
        "termCount": _term_count(glossary),
    }


def _summarize_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return compact list response preserving pagination metadata."""
    return {
        "items": [_summarize_glossary(glossary) for glossary in _extract_items(data)],
        "pagination": data.get("pagination", {}) if isinstance(data, dict) else {},
    }


def execute(
    output_format: str = "console",
    limit: int = 100,
    page: int = 1,
    debug: bool = False,
    config_file: str = None,
) -> None:
    """List glossaries for the authenticated organization."""
    try:
        config = Config(config_file)
        if config.exists():
            config.load()

        glossary_service = GlossaryService(config, debug=debug)
        result = glossary_service.list_glossaries(limit=limit, page=page)
        summary = _summarize_response(result)

        if output_format == "json":
            click.echo(json.dumps(summary, ensure_ascii=False, indent=2))
            return

        glossaries = summary["items"]
        if not glossaries:
            click.echo(f"{Fore.YELLOW}No glossaries found.{Fore.RESET}")
            return

        click.echo(f"{Fore.GREEN}Found {len(glossaries)} glossaries:{Fore.RESET}")
        for glossary in glossaries:
            glossary_id = glossary.get("id", "")
            name = glossary.get("name", "Untitled glossary")
            status = glossary.get("status", "")
            languages = glossary.get("languages", [])
            languages_text = ", ".join(lang for lang in languages if lang)
            meta = f" [{languages_text}]" if languages_text else ""
            status_text = f" ({status})" if status else ""
            term_count = glossary.get("termCount", 0)
            click.echo(f"- {name}{status_text}{meta}: {glossary_id} ({term_count} terms)")

    except Exception as e:
        click.echo(f"{Fore.RED}Error listing glossaries: {str(e)}{Fore.RESET}")
