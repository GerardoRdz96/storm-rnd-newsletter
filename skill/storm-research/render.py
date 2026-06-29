#!/usr/bin/env python3
"""render.py — deterministic filler for the storm-research HTML briefing.

WAT-shaped: the workflow's verified JSON in, a clean self-contained-ish HTML
briefing out. Clones the template's *_BLOCK regions per item, HTML-escapes every
value (no injection, no markup breakage), and HARD-FAILS if any {{token}},
href="#", or block marker survives — so a partial fill can never ship stale text.

Usage:
    python3 render.py <briefing.json> <output.html> [--template report-template.html]
    python3 render.py --sample <output.html>        # render the bundled sample (for the gate)

Briefing JSON shape (the workflow's return):
    { topic, reader, goal/decision, summary, version?,
      findings: [{title, statement|final_statement, reliability|reliability_after,
                  supported_by:[], challenged_by:[], verdict?}],
      assumptions: [str], missing_lens: {name, why},
      sources_ledger: [{url, status, title?, note?}] }
"""
import sys, os, re, json, html, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, "report-template.html")

STATUS = {
    "confirmed": ("st--confirmed", "Confirmed"),
    "corrected": ("st--corrected", "Corrected"),
    "demoted":   ("st--demoted",   "Demoted"),
}

def esc(v):
    return html.escape("" if v is None else str(v))

def gauge(reliability):
    try:
        n = max(0, min(10, int(reliability)))
    except (TypeError, ValueError):
        n = 0
    cls = "" if n >= 7 else ("mid" if n >= 4 else "low")
    segs = "".join('<span class="seg on"></span>' if i <= n else '<span class="seg"></span>'
                   for i in range(1, 11))
    return cls, segs, n

def lens_tags(supported, challenged):
    out = []
    for s in (supported or []):
        out.append(f'<span class="tag tag--support">{esc(s)}</span>')
    for c in (challenged or []):
        out.append(f'<span class="tag tag--challenge">{esc(c)}</span>')
    return "".join(out) or '<span class="tag tag--support">—</span>'

def block(tpl, name):
    """Return (full_marker_region, inner_template) for <!--NAME-->...<!--/NAME-->."""
    m = re.search(rf"<!--{name}-->(.*?)<!--/{name}-->", tpl, re.S)
    if not m:
        raise SystemExit(f"render.py: template missing block {name}")
    return m.group(0), m.group(1)

def effective_reliability(f):
    r = f.get("reliability_after", f.get("reliability", 0))
    if f.get("verdict") == "demoted":
        try:
            r = min(int(r), 3)
        except (TypeError, ValueError):
            r = 1
    return r

def render(data, template_path):
    with open(template_path, encoding="utf-8") as fh:
        tpl = template_path and fh.read()

    # ── Findings (sorted by effective reliability desc) ──────────────────────
    findings = sorted(data.get("findings", []), key=effective_reliability, reverse=True)
    full, inner = block(tpl, "FINDING_BLOCK")
    rows = []
    for i, f in enumerate(findings, 1):
        rel = effective_reliability(f)
        cls, segs, n = gauge(rel)
        stmt = f.get("final_statement") or f.get("statement") or ""
        row = (inner
               .replace("{{RANK}}", f"#{i}")
               .replace("{{FINDING_TITLE}}", esc(f.get("title")))
               .replace("{{FINDING_BODY}}", esc(stmt))
               .replace("{{GAUGE_CLASS}}", cls)
               .replace("{{GAUGE_SEGS}}", segs)            # pre-rendered markup, not escaped
               .replace("{{RELIABILITY}}", str(n))
               .replace("{{LENS_TAGS}}", lens_tags(f.get("supported_by"), f.get("challenged_by"))))
        rows.append(row)
    tpl = tpl.replace(full, "\n".join(rows) if rows else
                      '<p style="color:#6e8299">No findings survived verification.</p>')

    # ── Assumptions ──────────────────────────────────────────────────────────
    full, inner = block(tpl, "ASSUMPTION_BLOCK")
    rows = [inner.replace("{{ASSUMPTION}}", esc(a)) for a in data.get("assumptions", [])]
    tpl = tpl.replace(full, "\n".join(rows) if rows else inner.replace("{{ASSUMPTION}}", "—"))

    # ── Sources ledger ───────────────────────────────────────────────────────
    full, inner = block(tpl, "SOURCE_BLOCK")
    rows = []
    for s in data.get("sources_ledger", []):
        cls, label = STATUS.get((s.get("status") or "").lower(), ("st--demoted", "Unverified"))
        url = (s.get("url") or "").strip() or "about:blank"
        title = s.get("title") or url
        rows.append(inner
                    .replace("{{SRC_STATUS_CLASS}}", cls)
                    .replace("{{SRC_STATUS_LABEL}}", esc(label))
                    .replace("{{SRC_URL}}", esc(url))
                    .replace("{{SRC_TITLE}}", esc(title))
                    .replace("{{SRC_NOTE}}", esc(s.get("note") or "")))
    tpl = tpl.replace(full, "\n".join(rows) if rows else inner
                      .replace("{{SRC_STATUS_CLASS}}", "st--demoted")
                      .replace("{{SRC_STATUS_LABEL}}", "None")
                      .replace("{{SRC_URL}}", "about:blank")
                      .replace("{{SRC_TITLE}}", "No sources checked")
                      .replace("{{SRC_NOTE}}", ""))

    # ── Scalars ──────────────────────────────────────────────────────────────
    ml = data.get("missing_lens") or {}
    sources_checked = data.get("sources_checked", len(data.get("sources_ledger", [])))
    today = datetime.date.today().isoformat()
    scal = {
        "{{TOPIC}}": esc(data.get("topic")),
        "{{READER}}": esc(data.get("reader")),
        "{{DECISION}}": esc(data.get("decision") or data.get("goal")),
        "{{DATE}}": esc(data.get("date") or today),
        "{{VERSION}}": esc(data.get("version") or "V2"),
        "{{LENS_COUNT}}": esc(data.get("lens_count", len(data.get("findings", [])))),
        "{{SOURCES_CHECKED}}": esc(sources_checked),
        "{{SUMMARY}}": esc(data.get("summary")),
        "{{MISSING_NAME}}": esc(ml.get("name") or "—"),
        "{{MISSING_WHY}}": esc(ml.get("why") or "No missing lens identified."),
    }
    for k, v in scal.items():
        tpl = tpl.replace(k, v)

    # Strip template scaffolding comments (incl. the doc block, which intentionally
    # contains {{token}}/href="#" examples) so they never leak into the briefing.
    tpl = re.sub(r"<!--.*?-->", "", tpl, flags=re.S)

    # ── Guard: nothing stale may survive ─────────────────────────────────────
    leftovers = []
    if "{{" in tpl: leftovers.append("unfilled {{token}}")
    if 'href="#"' in tpl: leftovers.append('placeholder href="#"')
    if re.search(r"<!--/?[A-Z_]+_BLOCK-->", tpl): leftovers.append("leftover block marker")
    if leftovers:
        raise SystemExit("render.py GUARD FAILED — would ship stale content: " + ", ".join(leftovers))
    return tpl

SAMPLE = {
    "topic": "Can AI coding agents be trusted to run unattended in production?",
    "reader": "a technical decision-maker",
    "decision": "whether to let an agent merge + deploy without a human gate",
    "version": "V2", "lens_count": 5, "sources_checked": 4, "date": "2026-06-29",
    "summary": "The evidence favors supervised autonomy over full autonomy today: agents reliably draft, test, and open PRs, but unattended merge-and-deploy still fails on the long tail (auth, migrations, ambiguous specs). The economic case holds only where a verification gate is cheap; the historian's warning is that every prior 'it runs itself now' wave under-priced the last 10%.",
    "findings": [
        {"title": "Agents are production-ready for draft-and-verify, not deploy-and-forget",
         "final_statement": "Four of five lenses converge: agents write, test, and open PRs at senior-junior quality, but a human or a second agent must hold the merge gate. The skeptic found no audited case of sustained unattended deploy without a verification loop.",
         "reliability_after": 9, "verdict": "confirmed",
         "supported_by": ["Practitioner", "Academic", "Skeptic"], "challenged_by": ["Economist"]},
        {"title": "The unit economics only work where the verification gate is cheap",
         "final_statement": "Unattended agents pay off when an automated check (tests, type-gates, a cross-lineage reviewer) catches failures for near-zero marginal cost. Where verification needs a human, the labor 'saved' reappears as review time.",
         "reliability_after": 7, "verdict": "confirmed",
         "supported_by": ["Economist", "Practitioner"], "challenged_by": ["Academic"]},
        {"title": "'Fully autonomous now' claims rest on demo-grade tasks",
         "final_statement": "Demoted after verification: the strongest 'agents run themselves' sources benchmarked greenfield toy repos, not long-lived production systems with migrations and auth. The claim survives only in a narrowed form.",
         "reliability_after": 4, "verdict": "demoted",
         "supported_by": ["Historian"], "challenged_by": ["Practitioner", "Skeptic"]},
    ],
    "assumptions": [
        "A reliable automated verification signal exists for the codebase (tests, types, or a second-model review). Remove it and every finding's reliability drops.",
        "'Production' means a real, long-lived system with state, migrations, and users — not a greenfield prototype where failure is free.",
        "Current-generation models (mid-2026 frontier tier); a step-change in reliability would re-open the deploy-and-forget question.",
    ],
    "missing_lens": {"name": "The on-call engineer at 3 a.m.",
        "why": "All five lenses reasoned from the build-time chair. None sat in the seat of the person paged when an unattended deploy breaks — whose tolerance for a 2% failure rate actually decides the policy."},
    "sources_ledger": [
        {"status": "confirmed", "title": "SWE-bench Verified leaderboard — agent pass rates", "url": "https://www.swebench.com", "note": "primary source supports the draft-quality claim verbatim"},
        {"status": "corrected", "title": "Vendor blog — 'ships features autonomously'", "url": "https://example.com/blog", "note": "corrected: refers to PR creation, not merge-to-prod; statement narrowed"},
        {"status": "demoted", "title": "Viral thread — 'I let it run for a week unattended'", "url": "https://example.com/thread", "note": "demoted: anecdotal, unaudited, toy repo; dropped from finding #3's support"},
        {"status": "confirmed", "title": "Peer-reviewed study on agent failure modes (2026)", "url": "https://arxiv.org/abs/0000.00000", "note": "supports the long-tail-failure finding"},
    ],
}

def main(argv):
    args = argv[1:]
    template = DEFAULT_TEMPLATE
    if "--template" in args:
        i = args.index("--template"); template = args[i + 1]; del args[i:i + 2]
    if args and args[0] == "--sample":
        data, out = SAMPLE, (args[1] if len(args) > 1 else "storm-sample.html")
    else:
        if len(args) < 2:
            raise SystemExit(__doc__)
        with open(args[0], encoding="utf-8") as fh:
            data = json.load(fh)
        out = args[1]
    htmlout = render(data, template)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(htmlout)
    print(f"render.py: wrote {out} ({len(htmlout)} bytes, {len(data.get('findings', []))} findings)")

if __name__ == "__main__":
    main(sys.argv)
