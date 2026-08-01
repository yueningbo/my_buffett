#!/usr/bin/env python3
"""Validate a web/years/YYYY letter page for structure and common ZH quality failures."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
YEARS = ROOT / "web" / "years"

FORBIDDEN_VIEW = [
    'data-view="en"',
    "panel-en",
    "中英对照",
    'data-view="split"',
    "panel-split",
]

# Mid-sentence MT leftovers (case-insensitive word boundaries)
LEFTOVER_EN = re.compile(
    r"\b("
    r"substantially|nevertheless|therefore|approximately|respectively|"
    r"largely|closing|payout|ruling|stubs|appraise|eleemosynary|"
    r"consummated|formulated|illustrate|entire|warranted|"
    r"earth-shaking|bread-and-butter|unfettered|correspondingly"
    r")\b",
    re.I,
)

EXPLICIT_CLUTTER = [
    "good year（",
    "bad year（",
]


def validate(year):
    errors = []
    warnings = []
    ydir = YEARS / str(year)
    index = ydir / "index.html"
    meta_path = ydir / "meta.json"

    if not ydir.is_dir():
        print("ERROR: missing directory %s" % ydir)
        return 1
    if not index.is_file():
        print("ERROR: missing %s" % index)
        return 1
    if not meta_path.is_file():
        print("ERROR: missing %s" % meta_path)
        return 1

    extras = [
        p.name
        for p in ydir.iterdir()
        if p.name not in ("index.html", "meta.json") and not p.name.startswith(".")
    ]
    if extras:
        errors.append(
            "extra files in year dir (keep only index.html + meta.json): %s" % extras
        )

    html = index.read_text(encoding="utf-8")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    if meta.get("year") not in (year, str(year)):
        errors.append("meta.year mismatch: %r vs folder %s" % (meta.get("year"), year))
    if meta.get("status") != "ready":
        warnings.append(
            "meta.status is %r (expected ready when shipping)" % meta.get("status")
        )

    for key in (
        "title",
        "lede",
        "blurb",
        "dow_display",
        "partnership_display",
        "aum_display",
        "prev",
        "next",
    ):
        if key not in meta or meta[key] in (None, ""):
            errors.append("meta missing %s" % key)

    for bad in FORBIDDEN_VIEW:
        if bad in html:
            errors.append("forbidden view chrome: %s" % bad)

    easy_only = 'data-easy-only="true"' in html or "panel-easy" in html
    legacy_tabs = "panel-guide" in html and "panel-zh" in html

    if easy_only:
        if "panel-easy" not in html:
            errors.append("easy page needs panel-easy")
        if "source-drawer" not in html or "original-body" not in html:
            errors.append("easy page needs folded ZH in source-drawer")
        if "data-thread-metrics" not in html:
            errors.append("missing data-thread-metrics host")
        easy_html = html.split("panel-easy", 1)[1].split("source-drawer", 1)[0]
        zh_for_tables = (
            html.split("source-drawer", 1)[1].split("year-pager", 1)[0]
            if "source-drawer" in html
            else ""
        )
        easy_tables = easy_html.count("<table")
        zh_tables = zh_for_tables.count("<table")
        if zh_tables and easy_tables < zh_tables:
            errors.append(
                "easy panel missing tables vs folded ZH (%d < %d) — easy must keep full info"
                % (easy_tables, zh_tables)
            )
        if easy_html.count("<h2") < 3:
            errors.append("easy panel has fewer than 3 <h2> sections")
    elif legacy_tabs:
        if 'data-view="guide"' not in html or 'data-view="zh"' not in html:
            errors.append("need guide and zh view tabs")
        if "data-thread-metrics" not in html:
            errors.append("missing data-thread-metrics host in guide")
    else:
        errors.append("need either panel-easy (+ source-drawer) or panel-guide + panel-zh")

    if "letter.js" not in html:
        errors.append("missing letter.js")

    title = meta.get("title") or ""
    if title and title not in html:
        warnings.append("meta.title not found in HTML hero")
    lede = meta.get("lede") or ""
    if lede and lede not in html:
        warnings.append("meta.lede not found in HTML hero")

    # Faithful ZH (tab panel or folded drawer)
    if "panel-zh" in html:
        zh = html.split("panel-zh", 1)[1]
        if "year-pager" in zh:
            zh = zh.split("year-pager", 1)[0]
    elif "source-drawer" in html:
        zh = html.split("source-drawer", 1)[1]
        if "year-pager" in zh:
            zh = zh.split("year-pager", 1)[0]
    else:
        errors.append("no ZH body (panel-zh or source-drawer)")
        zh = ""

    if zh.count("<h2>") < 3:
        errors.append("ZH body has fewer than 3 <h2> sections (looks incomplete)")
    if "<table" not in zh:
        warnings.append("ZH has no tables — confirm source letter has none")

    for phrase in EXPLICIT_CLUTTER:
        if phrase in zh:
            errors.append("bilingual clutter in ZH: %s…" % phrase)

    leftovers = sorted(set(LEFTOVER_EN.findall(zh)))
    if leftovers:
        errors.append("English leftovers in ZH panel: %s" % ", ".join(leftovers))

    # Reading-panel litter (guide or easy)
    reading = ""
    if "panel-easy" in html:
        reading = html.split("panel-easy", 1)[1].split("source-drawer", 1)[0]
    elif "panel-guide" in html:
        reading = html.split("panel-guide", 1)[1].split("panel-zh", 1)[0]
    if "largely" in reading:
        warnings.append("reading panel contains English word 'largely'")

    # Pager: prev year should link here if prev ready
    prev = meta.get("prev")
    if prev:
        prev_index = YEARS / str(prev) / "index.html"
        if prev_index.is_file():
            prev_html = prev_index.read_text(encoding="utf-8")
            needle = 'href="../%s/index.html"' % year
            if needle not in prev_html and (
                "待制作" in prev_html and str(year) in prev_html
            ):
                errors.append(
                    "prev year %s pager still disabled for %s" % (prev, year)
                )
            elif needle not in prev_html:
                warnings.append(
                    "prev year %s may not link Next → %s" % (prev, year)
                )

    # This year next disabled or linked
    nxt = meta.get("next")
    if nxt:
        next_dir = YEARS / str(nxt)
        if next_dir.is_dir() and (next_dir / "index.html").is_file():
            if ('href="../%s/index.html"' % nxt) not in html:
                warnings.append(
                    "next year %s exists but pager may not link it" % nxt
                )
        else:
            if "待制作" not in html:
                warnings.append("next year missing; pager should show 待制作")

    # Source letter presence
    data = ROOT / "data" / "letters" / "years" / str(year)
    if not data.is_dir():
        warnings.append("no data/letters/years/%s source folder" % year)
    else:
        mds = list(data.glob("*.md"))
        if not mds:
            warnings.append("no markdown letters under %s" % data)

    # Homepage catalog (web/catalog.json)
    catalog_path = ROOT / "web" / "catalog.json"
    if not catalog_path.is_file():
        errors.append("missing web/catalog.json — run python3 web/tools/sync_catalog.py")
    else:
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append("catalog.json unreadable: %s" % exc)
            catalog = None
        if catalog is not None:
            entries = catalog.get("years") or []
            entry = None
            for item in entries:
                if item.get("year") == year or item.get("year") == str(year):
                    entry = item
                    break
            if entry is None:
                errors.append(
                    "year %s missing from web/catalog.json — run sync_catalog.py"
                    % year
                )
            else:
                if meta.get("status") == "ready" and entry.get("status") != "ready":
                    errors.append(
                        "catalog status for %s is %r (meta is ready) — re-run sync"
                        % (year, entry.get("status"))
                    )
                for field in ("title", "blurb"):
                    if meta.get(field) and entry.get(field) != meta.get(field):
                        warnings.append(
                            "catalog.%s != meta.%s — re-run sync_catalog.py"
                            % (field, field)
                        )
                href = entry.get("href") or ""
                expect = "years/%s/index.html" % year
                if href and href != expect:
                    warnings.append("catalog.href is %r (expected %r)" % (href, expect))

    print("validate_year %s" % year)
    for w in warnings:
        print("  WARN  %s" % w)
    for e in errors:
        print("  ERROR %s" % e)
    if not errors and not warnings:
        print("  OK")
    elif not errors:
        print("  OK (with warnings)")
    return 1 if errors else 0


def main(argv):
    if len(argv) != 2 or not argv[1].isdigit():
        print("Usage: validate_year.py YYYY", file=sys.stderr)
        return 2
    return validate(int(argv[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
