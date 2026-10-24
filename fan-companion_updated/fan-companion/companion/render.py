"""Turn citations into hoverable fact chips and build the 'fact receipts' view."""
from __future__ import annotations

import html
import re

from companion.facts import FactStore

CSS = """
<style>
.fact{display:inline-block;font-size:.68em;line-height:1.3;padding:0 .45em;margin:0 .1em;border-radius:.7em;
 background:rgba(26,115,232,.12);color:#1a73e8;vertical-align:super;cursor:help;font-weight:600}
.badge{display:inline-block;font-size:.75em;padding:.15em .6em;border-radius:1em;margin:.35em .4em 0 0}
.b-ok{background:rgba(30,142,62,.12);color:#1e8e3e}.b-fix{background:rgba(249,171,0,.18);color:#b06000}
.b-bad{background:rgba(217,48,37,.12);color:#d93025}.b-ai{background:rgba(128,128,128,.14);color:inherit}
.ping{border-left:3px solid #1a73e8;padding:.35em .8em;margin:.35em 0;background:rgba(26,115,232,.05);border-radius:0 .5em .5em 0}
.ping.goal{border-color:#1e8e3e;background:rgba(30,142,62,.07)}.ping.against{border-color:#d93025}
.ping.alert{border-color:#f9ab00;background:rgba(249,171,0,.1);font-weight:600}
.small{font-size:.8em;opacity:.75}
</style>
"""

CITE = re.compile(r"\[([A-Z]\d+)\]")


def to_html(text: str, fs: FactStore) -> str:
    safe = html.escape(text, quote=False)

    def chip(m):
        f = fs.facts.get(m.group(1))
        if not f:
            return f'<span class="fact" style="background:rgba(217,48,37,.15);color:#d93025">{m.group(1)}?</span>'
        tip = html.escape(f"{f.label}: {f.display} — {f.source}", quote=True)
        return f'<span class="fact" title="{tip}">{f.id}</span>'

    safe = CITE.sub(chip, safe)
    return safe.replace("\n", "  \n")


def badges(reply) -> str:
    rep = reply.report
    if reply.status == "verified":
        cls, txt = "b-ok", f"✓ {rep.numbers_verified}/{rep.numbers_checked} numbers verified against data"
    elif reply.status == "corrected":
        cls, txt = "b-fix", f"↻ caught an error and corrected it · {rep.numbers_verified}/{rep.numbers_checked} verified"
    else:
        cls, txt = "b-bad", "⚠ unverifiable sentence removed"
    if rep.numbers_checked == 0 and reply.status == "verified":
        cls, txt = "b-ai", "opinion / no data claims"
    label = "Auto-generated" if "emplate" in reply.engine else "AI-generated"
    return (f'<span class="badge b-ai">{label} · {html.escape(reply.engine)}</span>'
            f'<span class="badge {cls}">{txt}</span>')


def receipts_rows(reply) -> list[dict]:
    rows = []
    for fid in reply.report.cited_ids:
        f = reply.facts.facts.get(fid)
        if f:
            rows.append({"ID": f.id, "Fact": f.label, "Value": f.display, "Source": f.source})
    return rows
