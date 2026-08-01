---
name: letter-year-page
description: >-
  Build or revise a hand-crafted Buffett partnership/Berkshire letter year page
  under web/years/YYYY/ (meta.json + index.html with easy-read + faithful Chinese).
  Use when the user asks to continue the next year, make/补/重做某一年度页面,
  improve 股东信中文译文质量, or sync the letter catalog.
---

# Letter year page

Hand-craft one year of the Buffett letters reading site. Quality bar is the rewritten **1963 / 1964** pages, not early machine-translation drafts.

## When to use

- 「继续下一年」「做 YYYY」「重做 / 润色 YYYY 中文」
- Any edit to `web/years/YYYY/` letter pages

Also obey project rule `.cursor/rules/letter-zh-fidelity.mdc`.

## Layout (do not invent)

| Path | Role |
|------|------|
| `data/letters/years/YYYY/*.md` | English source of truth (not shown on page) |
| `web/years/_template/` | Copy start point |
| `web/years/YYYY/meta.json` | Year metadata → feeds catalog + thread metrics |
| `web/years/YYYY/index.html` | Easy-read + folded ZH (1964+); or legacy guide + ZH |
| `web/catalog.json` | Homepage year directory (generated; do not hand-edit) |
| `web/index.html` | Site home; renders timeline/catalog from `catalog.json` |
| `web/assets/{css/letter.css,js/letter.js,glossary.json}` | Shared chrome |

**Primary experience (1964+):** **信息完整的最易读连续解读** — not PPT, not a skim summary, not a separate 导读 tab.

- `body[data-easy-only="true"]` + `.panel-easy`：短段、层次、白话——但**不丢信息**（每节论点、全部表格、关键数字与杂项都要进主阅读）。
- 易读 = 更好读的结构与措辞，≠ 摘要删减。
- Faithful ZH stays in a collapsed `<details class="source-drawer">` for核对措辞 — not a reading mode.
- Never add `en`, split, or 中英对照 panels.
- Older years may still use `guide` + `zh` tabs; JS supports both.
- Sample: `web/years/1964/`.

**Directory hygiene:** ship only `index.html` + `meta.json`. Delete leftover `_*.py` / fragment helpers.

## Workflow (follow in order)

Copy and track:

```
Year page YYYY:
- [ ] 1. Read EN annual letter (+ note mid-year letters)
- [ ] 2. meta.json
- [ ] 3. Full ZH into source-drawer (or .panel-zh on legacy pages)
- [ ] 4. Easy-read panel covering the whole argument
- [ ] 5. Wire prev year pager + this year pager
- [ ] 6. sync_catalog.py
- [ ] 7. validate script + manual fidelity spot-check
```

### 1. Read sources

- Prefer the **year-end** letter (often dated January of YYYY+1).
- Mid-year / notices: footnote in tip/footer only unless user asks for full translate.
- Extract: Dow / partnership / LP returns, AUM, ages, section headings, all tables, named deals.

### 2. `meta.json`

Copy `_template/meta.json`. Set `status: "ready"` only when ZH is complete.

Required fields: `year`, `era`, `era_label`, `status`, `title`, `lede`, `blurb`, `prev`, `next`, plus thread fields used by `letter.js`:

`age`, `dow_display`, `dow_detail`, `partnership_display`, `partnership_detail`, `aum_display`, `aum_detail`, `market_mood`, `thread_note`

Hero title/lede on the page must match meta.

### 3. Chinese body (hard gate)

1. Scaffold from `_template` or clone last ready year chrome (header, fonts, theme, view-bar, pager, footer script).
2. Keep `<div data-thread-metrics></div>` inside the easy/era context.
3. Translate **every** section, paragraph, list item, footnote, and table from the annual letter into the folded ZH (`source-drawer` / `.original-body`).
4. **Then** write the easy-read. Easy may summarize; it must not replace ZH.

Fidelity + style details: [zh-quality.md](zh-quality.md).

### 4. Easy panel (primary) + folded ZH

**Easy** — 信息完整的最易读 continuous scroll:

- Mirror every letter section (`h2` / 必要 `h3`)；表格与 table-note 全部放入 easy（可用 `.table-scroll`）
- 短段、kickers、`.stat-row`、`.say-plain` 提升可读性；不得靠「摘要」省略论点、数字、名单或杂项
- 读者应能只读 easy、不打开译文，仍掌握信里全部实质信息
- No view tabs when `data-easy-only`

**Folded ZH** (fidelity archive):

```html
<details class="source-drawer" id="full-zh">
  <summary>完整译文（供核对，默认不必展开）</summary>
  <div class="original-body source-drawer-body">…忠实译文…</div>
</details>
```

**Legacy guide** (pre-1964 pages): keep `.panel-guide` + `.panel-zh` tabs until migrated.

### 5. Pagers

- Prev year: Next becomes `<a class="next" href="../YYYY/index.html">…`
- This year: Prev → prior; Next → next ready year, or `<span class="next is-disabled">YYYY+1 · 待制作</span>`

### 6. Catalog（首页目录，必做）

新年页做好后必须同步首页目录，否则 `web/index.html` 时间轴/列表不会出现该年：

```bash
python3 web/tools/sync_catalog.py
```

确认：

- 终端打印的 `ready` 数包含本年份
- `web/catalog.json` 里该年 `status` 为 `ready`，且 `title` / `blurb` / thread 字段与 `meta.json` 一致
- 用 HTTP 打开 `web/index.html`：时间轴与下方**目录列表**（`.catalog-root`）都能点到该年——不要只看 json
- 不要手改 `catalog.json`；改元数据只改 `meta.json` 再跑 sync

### 7. Validate

```bash
python3 .cursor/skills/letter-year-page/scripts/validate_year.py YYYY
```

Fix all errors (including catalog missing the year). Warnings are strong hints—clear or justify.

Then manually: skim ZH vs EN for missing sections/numbers; read 2–3 hard paragraphs aloud for machine-translation tone.

## Chrome conventions

- Terms: `<button class="term" data-term="workout">…</button>` — keys in `web/assets/glossary.json` (`workout`, `general-issues`, `dow`, `control`, …). Override with `data-term-title` / `data-term-body` only for year-specific senses.
- Tables: `class="nums"`; wide → wrap `div.table-scroll`.
- Keep intentional English labels sparingly: Generals / Workouts / Controls, fund names, BPL.
- Year meta line example: `Buffett Partnership, Ltd. · Kiewit Plaza · YYYY · 写于 YYYY-MM-DD`
- Footer: learning translation disclaimer; name the annual letter date; mention other letters that year if any.

## Quality bar (reject if)

- Mid-sentence English leftovers (`substantially`, `largely`, `closing`, …)
- Bilingual clutter: `good year（好年）`
- Guide English littered into ZH body
- Missing tables or collapsed “摘要式” ZH
- `panel-en` / `data-view="en"` / 中英对照
- Helper scripts left under `web/years/YYYY/`
- Shipped a ready year but forgot `sync_catalog.py` (homepage directory stale)

## Reference pages

Style/completeness targets: `web/years/1963/` (legacy tabs), `web/years/1964/` (easy-read).
