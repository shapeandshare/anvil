from __future__ import annotations

import re
from pathlib import Path


SPECS_DIR = Path("docs/vault/Specs")


def is_main_spec_file(path: Path) -> bool:
    name = path.name
    m = re.match(r"^(\d{3}) (.+)\.md$", name)
    if not m:
        return False
    stem = path.stem
    if " - " in stem[len(m.group(1)) + 1:]:
        return False
    return True


def has_frontmatter_field(content: str, field: str) -> bool:
    fm_start = content.find("---")
    if fm_start != 0:
        return False
    fm_end = content.find("---", 3)
    if fm_end == -1:
        return False
    fm_text = content[3:fm_end]
    return bool(re.search(rf"^{re.escape(field)}:", fm_text, re.MULTILINE))


def add_frontmatter_field(content: str, field: str, value: str | int) -> str:
    fm_end = content.find("---", 3)
    if fm_end == -1:
        return content
    line = f"{field}: {value}"
    return content[:fm_end] + line + "\n" + content[fm_end:]


def main() -> None:
    spec_files = sorted(SPECS_DIR.rglob("*.md"))
    updated = 0
    skipped = 0

    for filepath in spec_files:
        if not is_main_spec_file(filepath):
            skipped += 1
            continue

        m = re.match(r"^(\d{3})", filepath.stem)
        if not m:
            skipped += 1
            continue
        spec_number = int(m.group(1))

        content = filepath.read_text(encoding="utf-8")

        needs_update = False
        if not has_frontmatter_field(content, "spec_number"):
            content = add_frontmatter_field(content, "spec_number", spec_number)
            needs_update = True
        if not has_frontmatter_field(content, "doc_type"):
            content = add_frontmatter_field(content, "doc_type", "spec")
            needs_update = True

        if not needs_update:
            print(f"OK   (already has both): {filepath.name}")
            skipped += 1
            continue

        filepath.write_text(content, encoding="utf-8")
        print(f"ADDED {filepath.name}: spec_number={spec_number}, doc_type=spec")
        updated += 1

    print(f"\nDone. Updated: {updated}, Skipped: {skipped}")


if __name__ == "__main__":
    main()