#!/usr/bin/env python3
"""Guard against Django template syntax leaking into cookiecutter-rendered files.

Cookiecutter renders the template with Jinja2 under StrictUndefined, and Jinja
shares Django's ``{{ }}`` / ``{% %}`` delimiters. So a Python comment, docstring or
string that contains Django template syntax makes generation fail with an
unhelpful ``'x' is undefined`` — a failure this repository hit three times during
its own construction.

Rules enforced here:

1. In files cookiecutter RENDERS (``.py``, ``.md``, ``.toml``, ``.yml``, Makefile …),
   every ``{{ … }}`` / ``{% … %}`` must either reference ``cookiecutter.``, be a
   Jinja control tag, or sit inside ``{% raw %}…{% endraw %}``.
   Prefer rewording the comment over wrapping it in ``{% raw %}``: these projects
   use the Django template engine, and cookiecutter's Jinja should not leak into
   the source a developer reads.

2. In files cookiecutter COPIES VERBATIM (anything matching ``_copy_without_render``
   — all HTML and everything under ``templates*/``), ``{{ cookiecutter.… }}`` is a
   bug: it will ship to the generated project as literal text.

Run: python tests/check_template_syntax.py
"""

import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO / "{{cookiecutter.project_slug}}"

# Binary and non-text suffixes cookiecutter never renders meaningfully.
SKIP_SUFFIXES = {".mo", ".png", ".jpg", ".jpeg", ".ico", ".gif", ".webp", ".woff", ".woff2", ".pdf"}

JINJA_CONTROL = re.compile(r"^\s*-?\s*(end)?(if|for|raw|else|elif|set|macro|call|filter)\b")
TOKEN = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)


def copied_verbatim(relative: pathlib.PurePath) -> bool:
    """Mirror the _copy_without_render patterns from cookiecutter.json."""
    parts = relative.parts
    return relative.suffix == ".html" or any(p.startswith("templates") for p in parts)


def main() -> int:
    config = json.loads((REPO / "cookiecutter.json").read_text(encoding="utf-8"))
    known = {k for k in config if not k.startswith(("_", "__"))}

    problems: list[str] = []
    rendered_count = copied_count = 0

    for path in sorted(TEMPLATE_DIR.rglob("*")):
        if not path.is_file() or path.suffix in SKIP_SUFFIXES:
            continue
        relative = path.relative_to(TEMPLATE_DIR)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if copied_verbatim(relative):
            copied_count += 1
            for match in TOKEN.finditer(text):
                if "cookiecutter." in match.group(0):
                    line = text[: match.start()].count("\n") + 1
                    problems.append(
                        f"{relative}:{line}: cookiecutter variable in a file that is "
                        f"copied verbatim - it will ship as literal text.\n"
                        f"    {match.group(0).strip()[:80]}"
                    )
            continue

        rendered_count += 1
        in_raw = False
        for match in TOKEN.finditer(text):
            token = match.group(0)
            inner = token[2:-2]
            if token.startswith("{%") and re.search(r"\braw\b", inner):
                in_raw = "endraw" not in inner
                continue
            if in_raw or "cookiecutter." in inner or JINJA_CONTROL.search(inner):
                continue
            line = text[: match.start()].count("\n") + 1
            problems.append(
                f"{relative}:{line}: template syntax cookiecutter will try to "
                f"evaluate. Reword it, or wrap it in {{% raw %}}.\n"
                f"    {token.strip()[:80]}"
            )

    # Catch typos like {{ cookiecutter.projet_slug }} before they reach a user.
    for path in sorted(TEMPLATE_DIR.rglob("*")):
        if not path.is_file() or path.suffix in SKIP_SUFFIXES:
            continue
        relative = path.relative_to(TEMPLATE_DIR)
        if copied_verbatim(relative):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in re.finditer(r"cookiecutter\.([a-zA-Z_][a-zA-Z0-9_]*)", text):
            if match.group(1) not in known:
                line = text[: match.start()].count("\n") + 1
                problems.append(
                    f"{relative}:{line}: unknown cookiecutter variable "
                    f"'{match.group(1)}' - not declared in cookiecutter.json."
                )

    # Django's {# #} comment is SINGLE-LINE ONLY. A multi-line one is not
    # tokenised as a comment: it renders verbatim into the page. We shipped
    # exactly that bug twice - once it wrapped a live {% include %} of the
    # template itself, which 500'd the newsletter sign-up with a RecursionError.
    for path in sorted(TEMPLATE_DIR.rglob("*.html")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(TEMPLATE_DIR)
        for match in re.finditer(r"\{#", text):
            rest = text[match.start():]
            close = rest.find("#}")
            if close == -1:
                continue
            if "\n" in rest[:close]:
                line = text[: match.start()].count("\n") + 1
                problems.append(
                    f"{relative}:{line}: multi-line {{# #}} comment. Django's is "
                    f"single-line only, so this renders verbatim into the page. "
                    f"Use {{% comment %}}...{{% endcomment %}}."
                )

    print(f"rendered files checked: {rendered_count}")
    print(f"verbatim files checked: {copied_count}")

    if problems:
        print(f"\n{len(problems)} problem(s):\n")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print("no template-syntax problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
