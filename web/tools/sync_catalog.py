#!/usr/bin/env python3
"""Scan web/years/*/meta.json and write web/catalog.json for the index page."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEARS_DIR = ROOT / "years"
OUT = ROOT / "catalog.json"

THREAD_KEYS = (
    "age",
    "dow_display",
    "dow_detail",
    "partnership_display",
    "partnership_detail",
    "aum_display",
    "aum_detail",
    "market_mood",
    "thread_note",
)


def main():
    years = []
    for path in sorted(YEARS_DIR.glob("*/meta.json")):
        folder = path.parent.name
        if folder.startswith("_"):
            continue
        meta = json.loads(path.read_text(encoding="utf-8"))
        year = int(meta.get("year") or folder)
        entry = {
            "year": year,
            "era": meta.get("era", "partnership"),
            "era_label": meta.get("era_label", ""),
            "status": meta.get("status", "stub"),
            "title": meta.get("title", str(year)),
            "blurb": meta.get("blurb", ""),
            "href": "years/%s/index.html" % year,
            "prev": meta.get("prev"),
            "next": meta.get("next"),
        }
        for key in THREAD_KEYS:
            if key in meta and meta[key] not in (None, ""):
                entry[key] = meta[key]
        years.append(entry)

    years.sort(key=lambda y: y["year"])
    catalog = {
        "title": "Buffett Letters",
        "updated_note": "Run: python3 web/tools/sync_catalog.py",
        "years": years,
        "ready_count": sum(1 for y in years if y["status"] == "ready"),
        "total": len(years),
    }
    OUT.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Wrote %s (%s years, %s ready)"
        % (OUT, catalog["total"], catalog["ready_count"])
    )


if __name__ == "__main__":
    main()
