# Installing the STORM Research skill

This is a [Claude Code](https://claude.com/claude-code) skill. Once installed, you run it with `/storm-research <topic>` (or just "storm research <topic>") and it produces a verified, multi-perspective HTML briefing.

## What's in the folder

```
skill/storm-research/
  SKILL.md                      the SOP Claude follows (the front door)
  storm-research.workflow.js    the engine: 5 lenses → contradiction map → synthesis → verify
  render.py                     deterministic HTML renderer (fills the template, guards against stale output)
  report-template.html          the briefing design (single-file, self-contained)
```

## Requirements

- **Claude Code** — a recent version with **dynamic Workflows** (the `Workflow` tool). Without it, the skill falls back to parallel `Task` calls (slower to wire, same result).
- **Python 3** (3.8+, tested on 3.9 and 3.12) — for `render.py` (no third-party packages needed).
- **Web search** available to subagents (standard in Claude Code).
- *Optional but recommended:* a second model CLI (e.g. Codex/GPT or Gemini) for the cross-model "final verdict" step. If you don't have one, skip Phase 4.5.

## Get the files

Clone (or download) this repo — the skill lives under `skill/storm-research/`:

```bash
git clone https://github.com/GerardoRdz96/storm-rnd-newsletter.git
cd storm-rnd-newsletter
```
(Or on GitHub: **Code → Download ZIP**, then unzip and `cd` in.)

## Install

**Option A — user-wide (available in every project):**
```bash
cp -r skill/storm-research ~/.claude/skills/
```

**Option B — project-local (just this repo/project):**
```bash
mkdir -p .claude/skills
cp -r skill/storm-research .claude/skills/
# then in SKILL.md, change the two "~/.claude/skills/..." paths to ".claude/skills/..."
```

Relaunch Claude Code if it doesn't pick the skill up automatically.

## Run it

```
/storm-research the future of vector databases for RAG in 2026
```
or just type: `storm research <your topic>`

Claude will scope the topic + reader, run the five lenses in parallel, map contradictions, synthesize, verify the citations, (optionally) get a cross-model verdict, and render an HTML briefing you can open and share.

## Tips

- **Tune the lenses per topic.** The default five are practitioner, academic, skeptic, economist, historian. Swap or add a seat (a security lens for a vendor review, a customer lens for a product call) by passing `args.lenses` as `[{key, mandate}, …]` — see the Notes in `SKILL.md`.
- **Preview the design** without a full run: `python3 render.py --sample preview.html`.
- **Keep it public.** The lenses use web search, so don't put confidential or customer data in the topic. For sensitive research, use your organization's approved tooling.

## How it works (the short version)

A single prompt researches from one angle and inherits your blind spots. STORM runs five independent expert perspectives, finds where they disagree, ranks findings by how well they survive scrutiny, and checks every source against its original (confirmed / corrected / demoted) before it trusts the answer. The method comes from Stanford's [STORM](https://github.com/stanford-oval/storm) (NAACL 2024); this skill is a faithful port of the principle.
