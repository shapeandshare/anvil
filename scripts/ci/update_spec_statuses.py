from __future__ import annotations

import re
from pathlib import Path

SPECS_DIR = Path("docs/vault/Specs")

# Specs with clear codebase implementation evidence:
# - Referenced in AGENTS.md Active Technologies
# - Corresponding code modules exist in the repo
# - Spec body indicates implementation
# Only specs with full speckit format (7+ artifacts: spec, plan, tasks,
# data-model, research, quickstart, + checklists or contracts) are shipped.
# Specs with <7 artifacts are incomplete — draft.
SHIPPED = {
    26,
    27,  # Client SDK (7), Deployment Backup Restore (8)
    39,
    40,
    41,
    42,
    43,  # Model warm-start (7), External registry (7), HF browser (7), Asset storage (7), Tokenizer (7)
    44,
    45,
    46,  # LoRA (7), Adapter export (7), Compute routing (7)
    53,
    54,
    55,  # Dataset prep (7), Eval (7), Teaching (7)
    57,
    58,  # Degraded mode (8), Secrets (7)
    60,
    61,  # Theme consistency (7), Startup recovery (7)
    63,
    64,  # Usable external models (8), MLflow catalog (8)
    81,
    82,  # Teach CTA (7), Paperclip bootstrap (8)
}

# Specs that were superseded by other specs
SUPERSEDED = {16}

# Specs that are deferred (not scheduled)
DEFERRED = {59, 65}

# Remaining specs stay as draft:
# 13 (governance - aspirational), 19 (LakeFS - not integrated)
# 28-37 (SaaS specs - aspirational/not fully built), 38 (fine-tuning arc - umbrella)
# 48-52 (GGUF/learning content - partially implemented)
# 62 (non-educational help guide - content spec)


def update_status(filepath: Path, new_status: str) -> bool:
    content = filepath.read_text(encoding="utf-8")
    # Replace the status line in frontmatter
    pattern = re.compile(r"^(status:)\s*\S+", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(f"status: {new_status}", content)
        filepath.write_text(content, encoding="utf-8")
        return True
    return False


def main() -> None:
    updated = 0
    skipped = 0

    for filepath in sorted(SPECS_DIR.rglob("*.md")):
        # Only update main spec files (have spec_number)
        if not filepath.name.startswith(
            ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")
        ):
            continue
        if " - " in filepath.stem[4:]:
            continue

        # Read spec_number from frontmatter
        content = filepath.read_text(encoding="utf-8")
        m = re.search(r"^spec_number:\s*(\d+)", content, re.MULTILINE)
        if not m:
            skipped += 1
            continue

        spec_number = int(m.group(1))

        if spec_number in SHIPPED:
            new_status = "shipped"
        elif spec_number in SUPERSEDED:
            new_status = "superseded"
        elif spec_number in DEFERRED:
            new_status = "deferred"
        else:
            skipped += 1
            continue

        if update_status(filepath, new_status):
            print(f"  {spec_number:3d} {new_status:12s} {filepath.name}")
            updated += 1
        else:
            print(f"  {spec_number:3d} FAILED      {filepath.name}")
            skipped += 1

    print(f"\nDone. Updated: {updated}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
