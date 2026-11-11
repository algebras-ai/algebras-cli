"""
Placeholder syntaxes.

Each syntax has a strict pattern (a valid placeholder) and, where useful, a lenient pattern that
also matches damaged variants (lookalike letters, fullwidth signs, stray spaces) so the checker
can find and repair them.
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional, Pattern

# Kinds whose relative order must stay the same when they are not positional
# (printf-style "%s ... %d" fills arguments by position in the string).
ORDERED_KINDS = frozenset({"printf"})


@dataclass(frozen=True)
class Syntax:
    name: str
    kind: str
    pattern: Pattern[str]
    lenient: Optional[Pattern[str]] = None


_PRINTF_FLAGS = r"[-+0#,]*"
_PRINTF_LENGTH = r"(?:hh|h|ll|l|q|L|z|t|j)?"

# Java Formatter, C and Objective-C/Swift printf in one pattern. The space and "'" flags are left
# out on purpose: "50% off" would otherwise match "% o".
PRINTF = Syntax(
    name="printf",
    kind="printf",
    pattern=re.compile(
        r"%%"
        r"|%(?:\d+\$)?[tT][a-zA-Z]"
        r"|%(?:\d+\$)?" + _PRINTF_FLAGS + r"\d*(?:\.\d+)?" + _PRINTF_LENGTH
        + r"[@diuUoOxXfFeEgGaAcCsSpbBhHn]"
    ),
    # Any letter (Cyrillic, Greek, fullwidth ...) after a printf prefix that has a position or a
    # length modifier, or a fullwidth percent sign. Kept narrow so normal words are not matched.
    lenient=re.compile(
        r"[%％]\s?(?:[0-9０-９]+\s?[$＄]\s?)" + _PRINTF_FLAGS + r"\d*(?:\.\d+)?" + _PRINTF_LENGTH + r"[^\W\d_]"
        r"|％(?:\d+\$)?" + _PRINTF_FLAGS + r"\d*(?:\.\d+)?" + _PRINTF_LENGTH + r"[^\W\d_@]"
        r"|[%％]\s?(?:[0-9０-９]+\s?[$＄]\s?)?[＠@]"
        r"|%\d*(?:\.\d+)?" + _PRINTF_LENGTH + r"[^\W\d_a-zA-Z]"
    ),
)

# %#@name@ references in .stringsdict NSStringLocalizedFormatKey.
OBJC_VARIABLE = Syntax(
    name="objc_variable",
    kind="objc_variable",
    pattern=re.compile(r"%(?:\d+\$)?#@[A-Za-z_][A-Za-z0-9_]*@"),
)

PYTHON_PERCENT = Syntax(
    name="python_percent",
    kind="named",
    pattern=re.compile(r"%\([^)\s]+\)[-+ 0#]*\d*(?:\.\d+)?[diouxXeEfFgGcrsa]"),
    lenient=re.compile(r"%\([^)]+\)\s?[^\W\d_]"),
)

RUBY = Syntax(
    name="ruby",
    kind="named",
    pattern=re.compile(r"%\{[^{}\s]+\}|%<[^<>\s]+>[-+ 0#]*\d*(?:\.\d+)?[a-zA-Z]"),
    lenient=re.compile(r"[%％]\s?\{\s*[^{}]+?\s*\}"),
)

I18NEXT = Syntax(
    name="i18next",
    kind="named",
    pattern=re.compile(r"\{\{-?\s*[^{}]+?\s*\}\}|\$t\([^()]*\)"),
    lenient=re.compile(r"\{\{\s*[^{}]+?\s*\}\}"),
)

JS_TEMPLATE = Syntax(
    name="js_template",
    kind="named",
    pattern=re.compile(r"\$\{[^{}]+\}"),
)

ICU_SIMPLE = Syntax(
    name="icu_simple",
    kind="named",
    pattern=re.compile(
        r"\{\s*(?:\d+|[A-Za-z_][A-Za-z0-9_.]*)\s*(?:,\s*(?:number|date|time)\s*(?:,[^{}]*)?)?\}"
    ),
    # A single word in braces (e.g. a translated name "{имя}"). ICU plural/select branch text
    # ("{# items}") has spaces or "#" and is not matched.
    lenient=re.compile(r"\{\s*[^\W\d][\w.]*\s*\}"),
)

SYMFONY = Syntax(
    name="symfony",
    kind="named",
    pattern=re.compile(r"%[A-Za-z_][A-Za-z0-9_.]*%"),
)

QT = Syntax(
    name="qt",
    kind="named",
    pattern=re.compile(r"%(?:L)?[1-9][0-9]?(?![0-9$])"),
)

CHROME = Syntax(
    name="chrome",
    kind="named",
    pattern=re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$[1-9]"),
)

# Opening, closing and self-closing markup tags (HTML, <b>, <xliff:g>, <x/>, <ph/> ...).
# The tag is one token; the text between an open and a close tag stays translatable.
XML_TAG = Syntax(
    name="xml_tag",
    kind="tag",
    pattern=re.compile(r"</?[A-Za-z][A-Za-z0-9_.:-]*(?:\s+[^<>]*?)?/?>"),
)

SYNTAXES: Dict[str, Syntax] = {
    s.name: s
    for s in (
        PRINTF,
        OBJC_VARIABLE,
        PYTHON_PERCENT,
        RUBY,
        I18NEXT,
        JS_TEMPLATE,
        ICU_SIMPLE,
        SYMFONY,
        QT,
        CHROME,
        XML_TAG,
    )
}


def get_syntax(name: str) -> Syntax:
    try:
        return SYNTAXES[name]
    except KeyError:
        raise ValueError(
            f"Unknown placeholder syntax '{name}'. Known: {', '.join(sorted(SYNTAXES))}"
        )
