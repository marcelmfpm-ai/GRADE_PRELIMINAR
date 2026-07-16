# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file HTML dashboard (`index.html`, ~7000 lines, ~680KB) tracking the class schedule ("Grade APC CFP2/2026") for a police training course. No build step, no bundler, no framework — plain HTML/CSS/JS opened directly in a browser (`open index.html` or a `file://` URL). The only external dependencies are loaded via CDN: Google Fonts and ExcelJS (`cdnjs.cloudflare.com/.../exceljs`).

There is no `package.json`, no test suite, and no linter. `generate-csv.js` is a standalone Node script (needs `npm install jsdom` — not vendored, no lockfile).

`disponibilidade-professor.html` is a second, independent standalone page (own `<style>`/`<script>`, no shared code with `index.html`) that lets a scheduler pick a professor's availability window (start/end date + cargo) and see which classes fall in it: a summary table (cargo/código/descrição/turmas/count) and a month-by-month calendar heatmap. It only ever shows dates from today forward. Its data is a `const DADOS_AULAS = [...]` array baked directly into the file between `/* BEGIN_DADOS_AULAS */` / `/* END_DADOS_AULAS */` markers — regenerated from `index.html`'s live calendar by `generate-professor-data.py` (Python + BeautifulSoup, not Node — see below). It was deliberately kept data-embedded (not `fetch('calendario.csv')`) so it keeps working when opened directly via `file://`, matching `index.html`'s own no-build, no-fetch convention.

## Commands

- **View the app**: `open index.html` (macOS) — just opens it in the default browser.
- **View the professor-availability tool**: `open disponibilidade-professor.html`.
- **Regenerate `calendario.csv` locally**: `npm install jsdom && node generate-csv.js` (run from repo root). Requires Node; nothing else in this repo does.
- **Regenerate `disponibilidade-professor.html`'s embedded data**: `python3 generate-professor-data.py` (needs `beautifulsoup4`: `pip install beautifulsoup4`). Run this after any edit to `index.html`'s calendar cards — it only rewrites the `DADOS_AULAS` block between the markers, so hand-edits to the rest of the file survive. Node isn't available in every environment this repo is worked in; this script is the reason a Python path exists in parallel to the Node one used for `calendario.csv`.
- No build, lint, or test commands exist.

### CI

`.github/workflows/generate-csv.yml` runs on every push to `main` that touches `index.html`: it installs `jsdom`, runs `node generate-csv.js`, and auto-commits the resulting `calendario.csv` (commit message `Auto: atualizar calendario.csv`). So `calendario.csv` is a derived artifact — you generally don't need to hand-edit it, but if you edit `index.html`'s calendar and want the CSV in sync before pushing (e.g. no Node available locally), replicate `extractCalendarRows`/`mergeConsecutiveRows` in another language and diff against a known-good baseline before trusting the output.

## Architecture

### The Calendário tab is the single source of truth

`index.html` has six tabs (Visão Geral, Grade Detalhada, Por Semana, Gantt, Calendário, Gráficos). All the HTML you see in the first five tabs when you open the file is a **stale, pre-baked snapshot** — on page load, `refreshDadosFromCalendario()` (called at top level, near the end of the `<script>` block) scans the **Calendário tab's DOM** (`#cal-container .cal-week` → `.cal-entry` cards) and rebuilds the in-memory `DADOS` array from scratch. `renderAll()` (also called at top level, right after it's defined) then re-renders every other tab's HTML from `DADOS`, overwriting whatever static markup was in the file.

**Practical implication**: editing the static table/gantt/chart HTML in the other tabs has no effect on the running app — it gets clobbered on load. To change what class data the app shows, edit the `.cal-entry` cards inside `#cal-container` (aba Calendário). To change *derived-view rendering* (formatting, layout), edit the `render*` functions (`renderTabela`, `renderTimeline`, `renderGanttDots`, `renderGanttBars`, `renderMetrics`, `renderChSem`, etc.), not the static HTML.

### Calendar card structure

Each class session is a `<div class="cal-entry" data-dd-id="...">` inside a `<td class="cal-td">`, containing three spans:

```html
<div class="cal-entry" data-dd-id="calcard-<base64>">
  <span class="cal-cod">M2.1</span>
  <span class="cal-turma">PPF-A</span>
  <span class="cal-desc">Exerc. Simulado MBA - Crimes Ambientais</span>
</div>
```

- `cal-turma` is `CARGO-LETTER` (e.g. `EPF-A`, `PCF-B`). Cargo is derived by string-prefix match in `getCargo()` — always one of `EPF`, `DPF`, `PPF`, `PCF`.
- `cal-cod` is the module code (`M1.1`, `M2.3`, `M3.10`, …). The same code number is reused independently across cargos — e.g. `M2.1` for EPF and `M2.1` for PCF are unrelated activities with different descriptions. When bulk-editing codes, always match on `(cargo, code, description)` together, never on code alone, or you'll silently touch the wrong cargo's entries.
- `data-dd-id` is a stale snapshot ID; it is **not** authoritative. Drag/drop, copy, and edit operations recompute a fresh ID on the fly via `makeEntryId()`/`makeNewEntryId()` from the live `cal-cod`/`cal-turma`/`cal-desc` text, so you don't need to keep `data-dd-id` in sync when editing card text directly.
- Some cards (previously hand-edited via the in-app inline editor) carry an extra `spellcheck="false"` attribute on the spans — don't assume a fixed attribute set when parsing with regex; match on class name, not exact tag shape.

Weeks are `<div class="cal-week" id="cal-sem-N">` for N in `3..15` (there is no week 1 or 2 in this dataset). `SEM_INFO` and `SEMS` (top of the main `<script>` block) hold the week-number → date-range map and the canonical week list.

### Two independent implementations of CSV extraction

The logic that turns calendar cards into CSV rows (`extractCalendarRows` + `mergeConsecutiveRows` + the `.0`-padding of single-digit module codes, e.g. `M2.1` → `M2.01`) is duplicated in two places that must be kept in sync manually:

1. Inline in `index.html`'s `<script>` (used by the in-app "GERAR CSV" button in the Calendário tab, which also drives "GERAR XLSX").
2. `generate-csv.js` (used by CI / manual Node runs to produce `calendario.csv`).

`CONSECUTIVE_PAIRS` (`07:40→08:00`, `09:40→10:00`, `15:30→15:50`, `20:40→20:50`) defines which adjacent time slots get merged into a single row when the same class runs back-to-back. CSV rows are sorted by date then start time before being written; both implementations must stay sorted the same way. Output format: `;`-delimited, double-quoted fields, UTF-8 BOM, CRLF line endings.

### Filtering and cargo model

- `CARGOS = ['EPF','DPF','PPF','PCF']`, with fixed colors in `COLS` and turma counts in `BASE_TURMAS`.
- `DCIBER_PARES` hardcodes which module codes count as "DCIBER" per cargo (`{EPF:['M2.5','M2.6','M2.7'], DPF:['M2.5','M2.6'], PCF:[...], PPF:[...]}`) for the DCIBER quick-filter tag. This list is **not derived from card descriptions** — it's a manual code lookup. If you renumber/shift module codes for a cargo, you must update `DCIBER_PARES` for that cargo too, or the DCIBER filter will silently start matching the wrong (shifted) activities.
- The top filter bar (Cargo tags, Aula/Semana/Turma selects) all read/write `DADOS` via `filtrarDados()`; `sel-aula` options are regenerated by `syncAulaOptions()` from whatever module codes currently exist in `DADOS`, so it doesn't need manual updates when codes change.

### Calendar editing features (drag & drop IIFE)

The drag-and-drop editor (card move/copy/delete/inline-edit, undo, colored review markers, backlog panel) lives in a self-invoking function near the end of the script (`STORAGE_KEY = 'grade_apc_cfp2_2026_calendar_dragdrop_print_v3'` for layout persistence, separate `STORAGE_KEY = 'semanas_marcadas'` IIFE near the very end for the week-completion checkmarks). Layout state persists to `localStorage`, not to the file — "GERAR HTML ATUALIZADO" (`exportCurrentHtml`/`buildCleanHtml`) is what bakes the current DOM state back into a downloadable `index.html`, and "SALVAR NO GITHUB" (`saveToGithub`) commits that same generated HTML straight to the repo via the GitHub Contents API using a PAT stored in `localStorage` (`gh_token`, configured via `configureGithubToken()`).

Exporting CSV from the UI (`openCsvWeekPicker` → `exportCalendarCSV`) prompts for a specific week or "todas as semanas" via a small modal before generating the file — pass `semFiltro` (a week-id string or `'all'`) through if you touch this path.

**`buildCleanHtml()` must strip runtime-only DOM state before export, or "GERAR HTML ATUALIZADO" bakes in dead UI.** It clones `document.documentElement` and used to only strip a hardcoded blocklist of known browser-extension artifacts (Trust Wallet, an old `in-page-channel-node-id`, etc). That's insufficient: if the CSV week-picker modal (`#csv-week-modal`, created lazily by `openCsvWeekPicker` and appended to `<body>`) exists in the live DOM at export time — even closed — it gets serialized into the downloaded `index.html`. On next load, `openCsvWeekPicker` finds that pre-existing `#csv-week-modal` via `getElementById` and skips its whole creation branch (the `if(!modal){...}` block), so the modal opens visually but its Cancel/Confirm buttons have **no click handlers at all** — every click does nothing, indistinguishable from a frozen page. Any browser extension that injects DOM nodes (Glasp, Monica, Kantu, etc. have all been seen doing this into both `<head>` and `<body>`) has the same failure mode for whatever it injects. The fix (already in `buildCleanHtml`) is a whitelist, not a blocklist: only known-good direct children of `<body>` (`.header`, `.filtros-bar`, `.main`, `.footer`, `#panel-gantt`, `#panel-graficos`, `#panel-calendario`, plus `<script>`/`<style>` tags) survive the clone; everything else direct-child-of-`<body>` is dropped, and `monica-*`/`data-kantu` attributes are stripped from `<html>`/`<body>`. If "GERAR CSV" (or any other export button) silently does nothing — dropdown responds but buttons don't, no console error — suspect exactly this: a stale dynamically-created modal/overlay baked into the file by a prior export. Fix is to re-run `buildCleanHtml`'s whitelist logic (or manually delete the offending `<div id="...">` block) rather than debugging the export logic itself, which is usually fine.
