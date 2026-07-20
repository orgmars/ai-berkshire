#!/usr/bin/env python3
"""Generate WorkBuddy skills from AI Berkshire Claude command files.

This mirrors ``sync-codex-skills.py`` but targets WorkBuddy's native skill
layout so Claude Code / Codex / WorkBuddy users all share one canonical
workflow under ``skills/``.

Output: ``workbuddy-skills/<name>/SKILL.md`` (name + description frontmatter,
plus ``agent_created: true`` so WorkBuddy recognises it as a user skill).

Use ``--install`` to also copy each generated skill into the local WorkBuddy
skills directory (``~/.workbuddy/skills/<name>/``) so it is immediately usable.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILLS = ROOT / "skills"
WORKBUDDY_SKILLS = ROOT / "workbuddy-skills"
# Default install target; overridable via WORKBUDDY_SKILLS_DIR for portability.
INSTALL_ROOT = Path(os.environ.get("WORKBUDDY_SKILLS_DIR", Path.home() / ".workbuddy" / "skills"))


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 5 :].lstrip("\n")


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def yaml_quote(value: str) -> str:
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def metadata_for(name: str, source_name: str, source_text: str) -> str:
    existing, body = split_frontmatter(source_text)
    if existing:
        has_name = re.search(r"(?m)^name:\s*", existing) is not None
        has_description = re.search(r"(?m)^description:\s*", existing) is not None
        has_agent_created = re.search(r"(?m)^agent_created:\s*", existing) is not None
        lines = []
        if not has_name:
            lines.append(f"name: {name}")
        if not has_description:
            title = first_heading(body, name)
            lines.append(
                "description: "
                + yaml_quote(f"AI Berkshire skill: {title}. Source: skills/{source_name}.")
            )
        if not has_agent_created:
            lines.append("agent_created: true")
        lines.append(existing.rstrip())
        return "---\n" + "\n".join(lines) + "\n---\n\n"

    title = first_heading(source_text, name)
    description = f"AI Berkshire skill: {title}. Source: skills/{source_name}."
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {yaml_quote(description)}\n"
        "agent_created: true\n"
        "---\n\n"
    )


def workbuddy_body(name: str, source_name: str, source_text: str) -> str:
    _, body = split_frontmatter(source_text)
    note = (
        "## WorkBuddy adapter note\n\n"
        f"This skill is generated from `skills/{source_name}` so Claude Code, "
        "Codex and WorkBuddy users share one canonical workflow.\n\n"
        "- Treat `$ARGUMENTS` (or the arguments passed when this skill is "
        "loaded) as the user's research target, e.g. a company name or ticker.\n"
        "- When the source mentions Claude-only surfaces such as Task, Agent, "
        "WebSearch, Bash, Read or Write, map them to the closest WorkBuddy "
        "capability available in this session: multi-agent parallelism uses the "
        "WorkBuddy `Agent` tool (background parallel + optional team "
        "orchestration); web research uses WebSearch/WebFetch; local tools and "
        "file edits use Bash/Read/Write.\n"
        "- Shared project tools under `tools/` (e.g. financial_rigor.py) depend "
        "only on the Python standard library. In this environment run them with "
        "`python3 tools/...`; if `python3` is not on PATH (some Windows machines "
        "without a Python installer), use `python` or the WorkBuddy-managed "
        "Python instead. Always run from the repository root with paths like "
        "`python3 tools/financial_rigor.py ...`; if the current thread did not "
        "start inside the repo, locate the actual checkout path first instead "
        "of assuming a fixed home-directory path.\n"
        "- Before starting research, run the `date` command to confirm today's "
        'date; treat it as the baseline for "latest" data and state the data '
        "cutoff date in the report header. Never assume the current date from "
        "training data.\n"
        "- Preserve the research quality rules from `AGENTS.md`: cross-check "
        "financial data from two independent sources, use exact arithmetic "
        "tools for valuation/math, and clearly label uncertainty and source "
        "gaps.\n\n"
    )
    return note + body.rstrip() + "\n"


def main() -> None:
    check = "--check" in sys.argv[1:]
    install = "--install" in sys.argv[1:]
    unknown_args = [a for a in sys.argv[1:] if a not in ("--check", "--install")]
    if unknown_args:
        joined = ", ".join(unknown_args)
        raise SystemExit(f"Unknown argument(s): {joined}")

    if not check:
        WORKBUDDY_SKILLS.mkdir(exist_ok=True)

    count = 0
    stale: list[str] = []
    for source in sorted(CLAUDE_SKILLS.glob("*.md")):
        name = source.stem
        source_text = source.read_text(encoding="utf-8")
        content = metadata_for(name, source.name, source_text) + workbuddy_body(
            name, source.name, source_text
        )

        if check:
            target = WORKBUDDY_SKILLS / name / "SKILL.md"
            if not target.exists() or target.read_text(encoding="utf-8") != content:
                stale.append(str(target.relative_to(ROOT)))
            count += 1
            continue

        target_dir = WORKBUDDY_SKILLS / name
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "SKILL.md").write_text(content, encoding="utf-8")

        if install:
            dest_dir = INSTALL_ROOT / name
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target_dir / "SKILL.md", dest_dir / "SKILL.md")
        count += 1

    if check:
        if stale:
            print("WorkBuddy skills are out of date:")
            for path in stale:
                print(f"  {path}")
            raise SystemExit(1)
        print(f"Checked {count} WorkBuddy skills in {WORKBUDDY_SKILLS.relative_to(ROOT)}")
        return

    action = "Generated" if not install else "Generated and installed"
    print(f"{action} {count} WorkBuddy skills in {WORKBUDDY_SKILLS.relative_to(ROOT)}")
    if install:
        print(f"Installed into {INSTALL_ROOT}")


if __name__ == "__main__":
    main()
