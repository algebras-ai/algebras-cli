"""
Glossary download command implementation.
"""

import json
import os
from typing import Any, Dict, List

import click
from colorama import Fore

from algebras.config import Config
from algebras.services.glossary_service import GlossaryService


def _extract_terms(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return term items from common paginated API response shapes."""
    if isinstance(data.get("items"), list):
        return data["items"]
    if isinstance(data.get("terms"), list):
        return data["terms"]
    if isinstance(data.get("data"), list):
        return data["data"]
    if isinstance(data, list):
        return data
    return []


def execute(
    glossary_id: str,
    output: str,
    output_format: str = "console",
    limit: int = 100,
    debug: bool = False,
    config_file: str = None,
) -> None:
    """Download a glossary and its terms to a local JSON file."""
    try:
        config = Config(config_file)
        if config.exists():
            config.load()

        glossary_service = GlossaryService(config, debug=debug)
        glossary = glossary_service.get_glossary(glossary_id)

        terms = glossary.get("terms") if isinstance(glossary.get("terms"), list) else []
        if not terms:
            page_number = 1
            while True:
                page = glossary_service.list_terms(glossary_id, limit=limit, page=page_number)
                page_terms = _extract_terms(page)
                terms.extend(page_terms)
                pagination = page.get("pagination", {}) if isinstance(page, dict) else {}
                total_pages = pagination.get("totalPages")
                if total_pages is not None:
                    if page_number >= int(total_pages):
                        break
                elif len(page_terms) < min(limit, 100):
                    break
                page_number += 1

        payload = {
            "glossary": glossary,
            "terms": terms,
        }

        output_dir = os.path.dirname(output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        if output_format == "json":
            click.echo(json.dumps({"output": output, "glossaryId": glossary_id, "termCount": len(terms)}, indent=2))
            return

        click.echo(f"{Fore.GREEN}Downloaded glossary '{glossary_id}' with {len(terms)} terms to {output}{Fore.RESET}")

    except Exception as e:
        click.echo(f"{Fore.RED}Error downloading glossary: {str(e)}{Fore.RESET}")
