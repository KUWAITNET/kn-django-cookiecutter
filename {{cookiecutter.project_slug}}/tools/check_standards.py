#!/usr/bin/env python3
"""Check the KUWAITNET rules that settings and system checks cannot express.

``manage.py check`` sees configuration. ruff, bandit and pip-audit see code and
dependencies. This script covers the gap between them: rules the standards state
plainly, that nothing else fails a build over, and that were therefore the ones
actually broken in the reference project.

Every rule here is a defect that shipped, not a style preference:

* ``KN001`` a DRF serializer that publishes every column it is given.
* ``KN002`` an upload field with no validators. This is the worst one. Every
  public upload field in the reference project had zero validators, so an
  applicant's CV could be fetched by anyone who guessed a filename.
* ``KN003`` ``csrf_exempt`` with nothing recorded about why.
* ``KN004`` model-authored HTML rendered unescaped in a template - the route
  from an admin account to stored XSS.
* ``KN005`` a ``.env``, key or certificate committed to the repository.
* ``KN006`` a dependency the standards rejected, or never decided.
* ``KN007`` ``TODO:`` markers still in the handover documentation.

Nothing here re-implements a lint rule we already run. The ``ModelForm`` half of
KN001 is ruff ``DJ006``/``DJ007``; the Python half of KN004 is ruff ``S308``.
Both are selected in ``pyproject.toml`` and both fire today, so this script
deliberately stays quiet about them - a rule enforced in two places drifts, and
the duplicate report is what teaches people to stop reading the output. What is
left is what ruff has no rule for: ``DJ006``/``DJ007`` do not look at DRF
serializers, and ``S308`` cannot see a ``|safe`` in a template.

Errors fail the build. Warnings do not - they are things a reviewer must look
at, not things a machine can be certain about.

Stdlib only, on purpose: it has to run in a pre-commit hook, in CI, and on a
server, without an environment to install first.

Usage::

    python tools/check_standards.py                  # the gate
    python tools/check_standards.py --warnings-only  # early development
    python tools/check_standards.py --verbose        # every occurrence

The full map of which rule is enforced by which mechanism is in
``docs/enforcement.md`` in the KUWAITNET web standards repository.
"""

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None

ERROR = "error"
WARNING = "warning"

#: Never walked: dependencies, caches, collected output, and generated code.
#: Migrations are excluded because they mirror the models, and a model reported
#: twice trains people to stop reading the output.
SKIP_DIRS = {
    ".git",
    ".claude",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
    "htmlcov",
    "staticfiles",
    "media",
    "private-media",
    "migrations",
    "locale",
}

#: A class with one of these as a base publishes model fields over the API.
#: ModelForm is deliberately absent: ruff DJ006/DJ007 already own that case.
SERIALIZER_BASE = re.compile(r"(ModelSerializer|HyperlinkedModelSerializer)$")

#: Field classes that put a visitor-supplied file on our disk.
UNVALIDATED_FILE_FIELDS = {"FileField", "ImageField"}

#: A justification has to say something. One word is not a reason.
MIN_JUSTIFICATION_CHARS = 20

{%- raw %}

TEMPLATE_COMMENT = re.compile(r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}", re.S)
TEMPLATE_SHORT_COMMENT = re.compile(r"{#.*?#}", re.S)
SAFE_FILTER = re.compile(r"\|\s*safe\b")
AUTOESCAPE_OFF = re.compile(r"{%\s*autoescape\s+off\s*%}")
SHORT_COMMENT_OPEN = "{#"
{%- endraw %}

#: PEP 508 leaves a lot of ways to name the same package. Everything before the
#: first of these is the name.
REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9._-]+")

TODO_MARKER = re.compile(r"\bTODO:")


class Finding:
    """One violation, with everything needed to print and sort it."""

    def __init__(self, path: Path, line: int, rule: str, severity: str, message: str):
        self.path = path
        self.line = line
        self.rule = rule
        self.severity = severity
        self.message = message

    def render(self, root: Path) -> str:
        try:
            location = self.path.relative_to(root)
        except ValueError:
            location = self.path
        return f"{location}:{self.line}: [{self.rule}] {self.severity}: {self.message}"

    def sort_key(self):
        return (str(self.path), self.line, self.rule)


# --- Source discovery --------------------------------------------------------


def walk(root: Path, suffix: str):
    """Every file with ``suffix`` under ``root``, skipping generated trees."""
    for path in sorted(root.rglob(f"*{suffix}")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def parse(path: Path):
    """``(tree, source_lines)``, or ``(None, [])`` when the file will not parse.

    A syntax error is ruff's finding, not ours; reporting it twice helps nobody.
    """
    try:
        source = path.read_text(encoding="utf-8")
    # The trailing comma holds these parentheses open. Ruff's formatter removes
    # them when target-version is py314, and the bare `except A, B:` that leaves
    # behind is a parse error for a project generated on an older python_version.
    except (
        OSError,
        UnicodeDecodeError,
    ):
        return None, []
    try:
        return ast.parse(source, filename=str(path)), source.splitlines()
    except SyntaxError:
        return None, []


def comment_above(lines: list[str], lineno: int) -> str:
    """The contiguous comment block immediately above line ``lineno``.

    Decorator lines are stepped over, so a comment above a stack of decorators
    still counts as the justification for the one at the bottom.
    """
    collected: list[str] = []
    index = lineno - 2  # 0-based, one line up
    while index >= 0:
        stripped = lines[index].strip()
        if stripped.startswith("#"):
            collected.append(stripped.lstrip("#").strip())
        elif stripped.startswith("@") or not stripped:
            pass
        else:
            break
        index -= 1
    return " ".join(reversed(collected))


def justification_for(lines: list[str], lineno: int) -> str:
    """Any explanation attached to a line: trailing comment, or the block above."""
    if lineno - 1 < len(lines):
        inline = lines[lineno - 1]
        if "#" in inline:
            trailing = inline.split("#", 1)[1].strip()
            if len(trailing) >= MIN_JUSTIFICATION_CHARS:
                return trailing
    return comment_above(lines, lineno)


def call_name(node: ast.AST) -> str:
    """The last name of a call target: ``models.FileField`` -> ``FileField``."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


# --- KN001: a serializer that publishes every column -------------------------


def _classes_publishing_model_fields(tree: ast.Module) -> set[str]:
    """Names of module classes that are, or inherit from, a model serializer.

    Resolved to a fixed point so a project's own ``BaseArticleSerializer`` is
    caught as surely as a direct ``serializers.ModelSerializer`` subclass.
    """
    bases: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases[node.name] = [call_name(base) for base in node.bases]

    publishing = {
        name
        for name, parents in bases.items()
        if any(SERIALIZER_BASE.search(parent) for parent in parents)
    }
    changed = True
    while changed:
        changed = False
        for name, parents in bases.items():
            if name not in publishing and any(parent in publishing for parent in parents):
                publishing.add(name)
                changed = True
    return publishing


def _meta_is_model_bound(meta: ast.ClassDef) -> bool:
    """A ``Meta`` with ``model =`` binds to a model, whatever its outer class is."""
    for statement in meta.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "model" for target in statement.targets
        ):
            return True
    return False


def check_allowlists(path: Path, tree: ast.Module) -> list[Finding]:
    findings: list[Finding] = []
    publishing = _classes_publishing_model_fields(tree)
    # A base class imported from another module cannot be resolved here, so a
    # model-bound Meta in a serializers module counts on its own.
    module_is_public_surface = path.stem == "serializers"

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if not isinstance(statement, ast.ClassDef) or statement.name != "Meta":
                continue
            model_bound = _meta_is_model_bound(statement)
            if node.name not in publishing and not (module_is_public_surface and model_bound):
                continue
            findings.extend(_meta_violations(path, node.name, statement))

    # filterset_fields / ordering_fields sit on the view, not in Meta, and
    # publish every column just as effectively.
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if not isinstance(statement, ast.Assign):
                continue
            for target in statement.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id in ("filterset_fields", "ordering_fields")
                    and isinstance(statement.value, ast.Constant)
                    and statement.value.value == "__all__"
                ):
                    findings.append(
                        Finding(
                            path,
                            statement.lineno,
                            "KN001",
                            ERROR,
                            f'{node.name}.{target.id} = "__all__" publishes every column as a '
                            f"filter, including ones added later. List the fields explicitly.",
                        )
                    )
    return findings


def _meta_violations(path: Path, owner: str, meta: ast.ClassDef) -> list[Finding]:
    findings: list[Finding] = []
    for statement in meta.body:
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if not isinstance(target, ast.Name):
                continue
            if (
                target.id == "fields"
                and isinstance(statement.value, ast.Constant)
                and statement.value.value == "__all__"
            ):
                findings.append(
                    Finding(
                        path,
                        statement.lineno,
                        "KN001",
                        ERROR,
                        f'{owner}.Meta.fields = "__all__" makes every column the model '
                        f"has today, and every column anyone adds later, both readable "
                        f"and writable over the API - mass assignment, OWASP API3. "
                        f"Replace it with an explicit list, and split the read and write "
                        f"serializers if they differ. ruff's DJ007 covers ModelForm; "
                        f"nothing but this covers a serializer.",
                    )
                )
            elif target.id == "exclude":
                findings.append(
                    Finding(
                        path,
                        statement.lineno,
                        "KN001",
                        ERROR,
                        f"{owner}.Meta.exclude is a denylist: a column added to the model "
                        f"next year is published by default and nobody is asked. Use "
                        f"Meta.fields with an explicit list instead. ruff's DJ006 covers "
                        f"ModelForm; nothing but this covers a serializer.",
                    )
                )
    return findings


# --- KN002: an upload field with no validators -------------------------------


def check_upload_fields(path: Path, tree: ast.Module) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = call_name(node.func)
        if name not in UNVALIDATED_FILE_FIELDS:
            continue
        if any(keyword.arg == "validators" for keyword in node.keywords):
            continue
        findings.append(
            Finding(
                path,
                node.lineno,
                "KN002",
                ERROR,
                f"{name} with no validators. Size, extension allowlist and content "
                f"sniffing are all absent, so the browser's word for what this file is "
                f"is the only word there is - which is how the reference project served "
                f"applicant CVs to anyone who guessed a filename. Use "
                f"apps.core.validators.Secure{name} (add private=True for personal "
                f"data), or pass validators=[SecureFileValidator(...)] explicitly.",
            )
        )
    return findings


# --- KN003: csrf_exempt without a recorded reason ----------------------------


def check_csrf_exempt(path: Path, tree: ast.Module, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)) and call_name(node) == "csrf_exempt":
            lineno = node.lineno
            if lineno in seen:
                continue
            seen.add(lineno)
            if len(justification_for(lines, lineno)) >= MIN_JUSTIFICATION_CHARS:
                continue
            findings.append(
                Finding(
                    path,
                    lineno,
                    "KN003",
                    ERROR,
                    "csrf_exempt with no reason recorded. There are legitimate cases - a "
                    "provider callback, RFC 8058 one-click unsubscribe - and they all "
                    "share one property: something other than a session proves the "
                    "request. Write that something in a comment directly above this "
                    "line, or remove the decorator.",
                )
            )
    return findings


# --- KN004: unescaped model-authored HTML in a template ----------------------


def _explained_in_template(source: str, position: int) -> bool:
    """True when a substantial template comment sits immediately before ``position``.

    Same bargain as KN003: the construct is allowed, the silence is not. A
    comment that says which values reach the tag and why they are already safe
    is the record a reviewer needs; the checker's job is to make sure one exists.
    """
    line_start = source.rfind("\n", 0, position) + 1
    previous_start = source.rfind("\n", 0, max(line_start - 1, 0)) + 1
    # The comment has to end within the previous line or this one - a note three
    # screens up is not an explanation of this tag.
    adjacent = source[previous_start:position]
    if SHORT_COMMENT_OPEN not in adjacent and "endcomment" not in adjacent:
        return False
    # Measure the substance over the whole comment, which usually starts earlier.
    text = re.sub(r"[{}%#]", " ", source[max(0, previous_start - 400) : position])
    return len(text.strip()) >= MIN_JUSTIFICATION_CHARS


def check_unescaped_templates(path: Path) -> list[Finding]:
    """``|safe`` and ``autoescape off``: the half ruff's S308 cannot see.

    ``mark_safe`` in Python is already ruff S308, which is selected and fires.
    A template filter is invisible to every Python linter, and it is the same
    defect: markup that came out of the database, rendered as markup.
    """
    try:
        original = path.read_text(encoding="utf-8")
    except (
        OSError,
        UnicodeDecodeError,
    ):
        return []

    # Blank the comments rather than dropping them, so line numbers survive and
    # a rule quoted in a comment is not reported as a use of it.
    def blank(match):
        return re.sub(r"[^\n]", " ", match.group(0))

    source = TEMPLATE_COMMENT.sub(blank, original)
    source = TEMPLATE_SHORT_COMMENT.sub(blank, source)

    findings: list[Finding] = []
    for pattern, what in ((SAFE_FILTER, "|safe"), (AUTOESCAPE_OFF, "autoescape off")):
        for match in pattern.finditer(source):
            line = source[: match.start()].count("\n") + 1
            if _explained_in_template(original, match.start()):
                continue
            findings.append(
                Finding(
                    path,
                    line,
                    "KN004",
                    WARNING,
                    f"'{what}' renders its value as markup. Everything the CMS produces "
                    f"is already safe without it, so this is either unnecessary or it is "
                    f"stored XSS waiting for an editor account. Remove it, or explain it "
                    f"in a template comment on the line above.",
                )
            )
    return findings


# --- KN005: secrets committed to the repository ------------------------------


def check_tracked_secrets(root: Path) -> list[Finding]:
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "ls-files", "-z"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return []
    if result.returncode != 0:
        return []

    findings: list[Finding] = []
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        # A vendored certificate inside a checked-in dependency tree is somebody
        # else's file and a different argument; this rule is about ours.
        if any(part in SKIP_DIRS for part in Path(entry).parts):
            continue
        path = root / entry
        name = Path(entry).name
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            findings.append(
                Finding(
                    path,
                    1,
                    "KN005",
                    ERROR,
                    "an environment file is tracked in git. It holds the values that are "
                    "meant to differ per environment, and deleting it now does not remove "
                    "it from history. Untrack it (git rm --cached), rotate every "
                    "credential it contains, and keep .env.example as the documented "
                    "shape.",
                )
            )
        elif Path(entry).suffix in (".pem", ".key"):
            findings.append(
                Finding(
                    path,
                    1,
                    "KN005",
                    ERROR,
                    "a private key or certificate is tracked in git. Anyone who has ever "
                    "cloned this repository has it. Untrack it, reissue the key, and hand "
                    "the replacement over through the credential channel in the handover "
                    "checklist.",
                )
            )
    return findings


# --- KN006: dependencies against the approved list ---------------------------


def normalise_package(name: str) -> str:
    """PEP 503 normalisation, extras dropped, so ``bandit[toml]`` is ``bandit``."""
    match = REQUIREMENT_NAME.match(name.strip())
    if not match:
        return ""
    return re.sub(r"[-_.]+", "-", match.group(0)).lower()


def load_approved(packages_file: Path) -> dict[str, dict]:
    if tomllib is None or not packages_file.is_file():
        return {}
    try:
        data = tomllib.loads(packages_file.read_text(encoding="utf-8"))
    except (
        OSError,
        tomllib.TOMLDecodeError,
    ):
        return {}
    return {normalise_package(entry["name"]): entry for entry in data.get("packages", [])}


def _declared_requirements(pyproject: Path) -> list[str]:
    if tomllib is None:
        return []
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (
        OSError,
        tomllib.TOMLDecodeError,
    ):
        return []
    requirements = list(data.get("project", {}).get("dependencies", []))
    for group in data.get("dependency-groups", {}).values():
        requirements.extend(item for item in group if isinstance(item, str))
    return requirements


def check_dependencies(root: Path, packages_file: Path) -> list[Finding]:
    pyproject = root / "pyproject.toml"
    approved = load_approved(packages_file)
    if not approved or not pyproject.is_file():
        return []

    lines = pyproject.read_text(encoding="utf-8").splitlines()
    findings: list[Finding] = []
    for requirement in _declared_requirements(pyproject):
        name = normalise_package(requirement)
        if not name:
            continue
        entry = approved.get(name)
        lineno = next(
            (i + 1 for i, line in enumerate(lines) if requirement.split(">")[0][:24] in line), 1
        )
        if entry is None:
            findings.append(
                Finding(
                    pyproject,
                    lineno,
                    "KN006",
                    WARNING,
                    f"'{name}' is in no tier of the approved-package list, so nobody has "
                    f"decided it. That is not a refusal - it is an unanswered question. "
                    f"Answer the five checks in approved-packages.md section 4, record it "
                    f"in docs/14-decisions.md, and open a pull request against the "
                    f"standards so the next project gets the answer instead of the "
                    f"argument.",
                )
            )
        elif entry.get("tier") == "rejected":
            findings.append(
                Finding(
                    pyproject,
                    lineno,
                    "KN006",
                    ERROR,
                    f"'{name}' is on the rejected list: {entry.get('reason', '')} If that "
                    f"reason no longer holds, change approved-packages.md and this "
                    f"project together - do not work around it here.",
                )
            )
    return findings


# --- KN007: unfinished handover documentation --------------------------------


def check_documentation_todos(root: Path, verbose: bool) -> list[Finding]:
    docs = root / "docs"
    if not docs.is_dir():
        return []

    occurrences: list[tuple[Path, int]] = []
    for path in walk(docs, ".md"):
        try:
            text = path.read_text(encoding="utf-8")
        except (
            OSError,
            UnicodeDecodeError,
        ):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if TODO_MARKER.search(line):
                occurrences.append((path, number))

    if not occurrences:
        return []

    if verbose:
        return [
            Finding(
                path,
                line,
                "KN007",
                WARNING,
                "a TODO: marker is still here. Documentation with holes in it is the "
                "thing the client is handed.",
            )
            for path, line in occurrences
        ]

    files = len({path for path, _ in occurrences})
    first_path, first_line = occurrences[0]
    return [
        Finding(
            first_path,
            first_line,
            "KN007",
            WARNING,
            f"{len(occurrences)} TODO: markers remain across {files} documentation "
            f"file(s). Expected while the project is being built; a blocker at handover, "
            f"because these documents are a deliverable. Run with --verbose to list them.",
        )
    ]


# --- Driver ------------------------------------------------------------------


def collect(root: Path, packages_file: Path, verbose: bool) -> list[Finding]:
    findings: list[Finding] = []

    for path in walk(root, ".py"):
        tree, lines = parse(path)
        if tree is None:
            continue
        findings.extend(check_allowlists(path, tree))
        findings.extend(check_upload_fields(path, tree))
        findings.extend(check_csrf_exempt(path, tree, lines))

    for path in walk(root, ".html"):
        findings.extend(check_unescaped_templates(path))

    findings.extend(check_tracked_secrets(root))
    findings.extend(check_dependencies(root, packages_file))
    findings.extend(check_documentation_todos(root, verbose))

    return sorted(findings, key=Finding.sort_key)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the KUWAITNET standards that settings cannot express.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Project root to check (default: the repository this script is in).",
    )
    parser.add_argument(
        "--packages",
        type=Path,
        default=None,
        help="approved-packages.toml to check dependencies against "
        "(default: the copy next to this script).",
    )
    parser.add_argument(
        "--warnings-only",
        action="store_true",
        help="Report everything, fail on nothing. For early development only - CI "
        "must never pass this flag.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="List every occurrence instead of summarising the repetitive ones.",
    )
    arguments = parser.parse_args(argv)

    root = arguments.root.resolve()
    packages_file = arguments.packages or Path(__file__).resolve().parent / "approved-packages.toml"

    if tomllib is None:
        print("note: no tomllib in this interpreter, so KN006 (dependencies) was skipped.")

    findings = collect(root, packages_file, arguments.verbose)
    errors = [f for f in findings if f.severity == ERROR]
    warnings = [f for f in findings if f.severity == WARNING]

    for finding in findings:
        print(finding.render(root))

    if not findings:
        print("check_standards: no violations")
        return 0

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    print("Rules and how each is enforced: docs/enforcement.md in the KUWAITNET standards.")

    if arguments.warnings_only:
        print("--warnings-only: not failing. Remove the flag before this reaches CI.")
        return 0
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
