#!/usr/bin/env python3
"""Deterministic UX lint — mechanical S4 pre-filter. Zero pip deps (stdlib only).

Pattern-based (not a full parser): catches the subset of the S4 rules in
ux-rules.md that are detectable without a model. Fast, free, reproducible —
suitable as an automatic CI gate and a local pre-commit check, ahead of the
optional AI review (ci/ux_review.py).

Covers: non-semantic click handlers, viewport zoom-disable, raw |safe /                                          # ux-lint:allow-next docstring description contains banned patterns, not actual usage
{% autoescape false %} / Markup() / autoescape=False, aria-live="assertive",
and outline removal.

Intentionally conservative: it flags for human audit rather than guessing
context. Suppress a verified case with `ux-lint:allow` on the finding's own line,
or `ux-lint:allow-next` on the line directly above (for mid-tag findings):

    {{ value | safe }}        {# ux-lint:allow sanitized in service layer #}
    *:focus { outline: 0 }    /* ux-lint:allow box-shadow focus ring below */
    {# ux-lint:allow-next legacy widget, refactor tracked in #214 #}
    <div onclick="legacy()">…</div>

Exit codes: 0 clean (after suppressions), 1 unsuppressed S4 found, 2 usage error.

Usage:
  ux_lint.py FILE [FILE ...]
  git diff --name-only "$BASE" "$HEAD" \\
    | grep -E '\\.(html|htm|jinja|jinja2|j2|css|scss|sass|less|js|jsx|ts|tsx|vue|svelte|py)$' \\
    | xargs -r ux_lint.py
"""
import os
import re
import sys

ALLOW = re.compile(r"ux-lint:\s*allow(?!-next)", re.IGNORECASE)      # suppresses its own line
ALLOW_NEXT = re.compile(r"ux-lint:\s*allow-next\b", re.IGNORECASE)   # suppresses the following line

# Delimited comments are blanked before matching so a *mention* of a banned
# pattern inside a comment doesn't false-positive. Suppression annotations
# (which live in comments) are detected from the ORIGINAL text, not the blanked
# copy, so blanking does not defeat them. (// line comments are NOT stripped —
# too risky around `://` in strings/URLs.)
COMMENT_SPANS = [
    re.compile(r"{#.*?#}", re.DOTALL),                                       # Jinja {# #}
    re.compile(r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}", re.DOTALL | re.IGNORECASE),
    re.compile(r"<!--.*?-->", re.DOTALL),                                    # HTML
    re.compile(r"/\*.*?\*/", re.DOTALL),                                     # CSS / JS block
]


def blank_comments(text):
    """Replace delimited-comment spans with same-length runs, preserving
    newlines (so line numbers stay accurate)."""
    def _blank(m):
        return "".join("\n" if ch == "\n" else " " for ch in m.group(0))
    for rx in COMMENT_SPANS:
        text = rx.sub(_blank, text)
    return text


TEMPLATE = {".html", ".htm", ".jinja", ".jinja2", ".j2"}
MARKUP = TEMPLATE | {".jsx", ".tsx", ".vue", ".svelte"}
STYLE = {".css", ".scss", ".sass", ".less"}

# (id, category, message, compiled_regex, {applicable extensions})
CHECKS = [
    (
        "click-handler",
        "a11y",
        "<div>/<span> with click handler — use <button>/<a> (keyboard-inaccessible)",
        re.compile(r"<(?:div|span)\b[^>]*?\s(?:onclick|@click|v-on:click|on:click)\s*=", re.IGNORECASE),
        MARKUP,
    ),
    (
        "viewport-zoom",
        "a11y",
        "viewport disables zoom (user-scalable=no / maximum-scale=1)",
        re.compile(r"user-scalable\s*=\s*(?:no|0)|maximum-scale\s*=\s*1\b", re.IGNORECASE),
        MARKUP,
    ),
    (
        "jinja-safe",
        "template",
        "|safe — audit that input is trusted/sanitized (XSS risk)",
        re.compile(r"\|\s*safe\b"),
        TEMPLATE,
    ),
    (
        "autoescape-off",
        "template",
        "{% autoescape false %} — escaping disabled",
        re.compile(r"{%-?\s*autoescape\s+false", re.IGNORECASE),
        TEMPLATE,
    ),
    (
        "py-markup",
        "template",
        "Markup() — bypasses autoescape; audit input",   # ux-lint:allow description string, not actual call
        re.compile(r"\bMarkup\s*\("),
        {".py"},
    ),
    (
        "py-autoescape",
        "template",
        "autoescape=False — escaping disabled at the environment",  # ux-lint:allow description string, not actual call
        re.compile(r"autoescape\s*=\s*False\b"),
        {".py"},
    ),
    (
        "aria-live-assertive",
        "sse",
        'aria-live="assertive" on updates — use polite + coalesce milestones',
        re.compile(r"""aria-live\s*=\s*['"]assertive""", re.IGNORECASE),
        MARKUP,
    ),
    (
        "outline-removed",
        "focus",
        "outline removed — verify a :focus-visible replacement exists",
        re.compile(r"outline\s*:\s*(?:none|0)|\boutline-none\b", re.IGNORECASE),
        STYLE | MARKUP,
    ),
]


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def is_suppressed(lines, lineno):
    """`ux-lint:allow` on the finding's own line, or `ux-lint:allow-next` on the
    line directly above, suppresses the finding."""
    cur = lines[lineno - 1] if 1 <= lineno <= len(lines) else ""
    prev = lines[lineno - 2] if lineno >= 2 else ""
    return bool(ALLOW.search(cur) or ALLOW_NEXT.search(prev))


def lint_file(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return [], 0
    lines = text.splitlines()        # original — suppression annotations live in comments
    scan = blank_comments(text)      # comments blanked — used for pattern matching
    findings = []
    n_suppressed = 0
    for _id, cat, msg, rx, exts in CHECKS:
        if ext not in exts:
            continue
        for m in rx.finditer(scan):
            lineno = line_of(scan, m.start())
            if is_suppressed(lines, lineno):
                n_suppressed += 1
                continue
            findings.append((lineno, cat, msg))
    findings.sort(key=lambda f: f[0])
    return findings, n_suppressed


def main(argv):
    files = argv[1:]
    if not files:
        print("ux-lint: no files — clean.")
        return 0
    total = 0
    total_suppressed = 0
    n_files = 0
    for path in files:
        if not os.path.isfile(path):
            continue
        n_files += 1
        findings, n_sup = lint_file(path)
        total_suppressed += n_sup
        if findings:
            for lineno, cat, msg in findings:
                print(f"{path}:{lineno} [S4] {cat} — {msg}")
                total += 1
        else:
            print(f"{path} ✓")
    gate = "FAIL" if total else "PASS"
    sup = f" ({total_suppressed} suppressed)" if total_suppressed else ""
    print(f"\n{n_files} files · S4:{total}{sup} · GATE: {gate}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
