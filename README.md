# Bridge Inspection Report Reorganizer

A Python pipeline that takes an **element-organized** bridge inspection PDF
(the standard FHWA/AASHTO format where each element has its own table) and
reorganizes it into a **station-organized** field report — one page per
walking stop along the bridge, with every element relevant to that stop
grouped together.

The motivation: inspectors in the field shouldn't have to flip between
"Element 12 — Deck" and "Element 107 — Girder" and "Element 330 — Railing"
just to see what's going on at Span 2. One page per station, all elements
at hand.

---

## Table of Contents

- [What it does](#what-it-does)
- [Why](#why)
- [Quick start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [How it works](#how-it-works)
- [Configuration](#configuration)
- [The interactive review step](#the-interactive-review-step)
- [Handling different report formats](#handling-different-report-formats)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## What it does

**Input**: a PDF inspection report where each AASHTO/owner element has its own table:

```
Element 12: Reinforced Concrete Deck
  Location | CS1  | CS2 | CS3 | CS4 | Notes
  Span 1   | 4800 | 100 |  0  |  0  | Minor map cracking...
  Span 2   | 4600 | 280 | 20  |  0  | Efflorescence visible...
  ...

Element 107: Steel Open Girder/Beam
  Location | CS1 | CS2 | CS3 | CS4 | Notes
  Span 1   | 820 |  30 |  0  |  0  | Paint intact...
  Span 2   | 810 |  80 | 10  |  0  | Section loss G3 near Pier 2...
  ...
```

**Output**: a new PDF reorganized by physical station along the bridge:

```
Cover + Table of Contents (lists every station with worst CS)

§ Abutment 1
    ▪ Substructure Elements: Abutment body, ...
    ▪ Interface Elements: Bearings, joint seal
    Field Notes: _______________________________
    Inspector initials: ___ Date: ___ Photos: □

§ Span 1
    ▪ Span Elements: Deck, Girder, Railing
    Field Notes: ...

§ Pier 1
    ▪ Substructure Elements: Column, Pier Cap
    ▪ Interface Elements: Bearings, Joint
    Field Notes: ...

... (Span 2 → Pier 2 → Span 3 → ...)

§ Whole-Bridge Elements
    ▪ Wearing Surface (full table preserved)
    ▪ Drainage System
    ▪ Paint System
```

Worst Condition State (CS1=Good through CS4=Severe) is color-coded green
through red so problem areas jump out at a glance.

---

## Why

The default element-organized format is great for **reporting** to the owner
(every element, every condition state, neatly classified) but terrible for
**field inspection**. When you're standing at Pier 2 wanting to know
everything about it — the cap, the columns, the bearings, the joint seal —
you have to flip through four different element sections in the original.

This tool inverts the organization. Same data, different axis. Plus:

- One page per walking stop with blank Field Notes lines for handwriting
- Color-coded condition state highlighting
- Worst-CS column in the TOC so you know where to spend time
- "As recorded" labels preserved so anomalies can be traced back

---

## Quick start

```bash
# Clone and install
git clone https://github.com/<you>/bridge-pipeline.git
cd bridge-pipeline
pip install -r requirements.txt

# Run on the included sample
python pipeline.py

# Run on your own report
python pipeline.py path/to/your_report.pdf my_field_report.pdf
```

If your report contains elements the tool can't auto-classify, it will pop
open a browser tab for you to classify them (see [The interactive review
step](#the-interactive-review-step) below). Your decisions are saved into
`config/config.yaml` so next time the tool gets smarter.

---

## Installation

### Requirements

- Python 3.10 or newer
- A modern web browser (Chrome, Firefox, Safari, Edge — anything reasonable)

### Dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt`:

```
pdfplumber>=0.10.0
reportlab>=4.0.0
pyyaml>=6.0
```

No other system dependencies. The interactive review UI uses Python's
built-in `http.server` — no Flask, no Node, no Electron.

### Installing on Windows

If `pip install pdfplumber` complains about a missing C compiler, the
Microsoft Visual C++ Build Tools may be needed for one of its
dependencies. Most users don't hit this because wheels are usually
available; if you do, [install Build Tools from
here](https://visualstudio.microsoft.com/visual-cpp-build-tools/).

---

## Usage

### Basic

```bash
python pipeline.py <input.pdf> [output.pdf]
```

- `<input.pdf>` — your element-organized inspection report
- `[output.pdf]` — output filename (default: `field_report.pdf`)

### Flags

- `--skip-review` — skip the interactive review step. Any elements the
  tool can't auto-classify will be **excluded** from the output. Useful
  for quick test runs or batch processing.

### Examples

```bash
# Run on the built-in sample
python pipeline.py

# Run on your report, save to a specific filename
python pipeline.py reports/bridge_12345_2026.pdf bridge_12345_field.pdf

# Quick test without the review UI
python pipeline.py reports/bridge_12345_2026.pdf --skip-review
```

### Running individual stages

Each stage can be run independently, useful for debugging:

```bash
python extract.py  input.pdf  element_data.json
python classify.py config/config.yaml config/aashto_defaults.yaml element_data.json classified.json
python regroup.py  classified.json stations.json config/config.yaml
python render.py   stations.json field_report.pdf
```

The intermediate JSON files are written to disk on every full run, so you
can inspect them.

---

## How it works

```
┌─────────────────┐
│   input.pdf     │   element-organized inspection report
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   [1] extract   │   Reads element headers + tables using pdfplumber.
│                 │   Position-aware (uses y-coordinates) to correctly
│                 │   pair tables that wrap across page boundaries.
└─────────────────┘
         │ element_data.json
         ▼
┌─────────────────┐
│  [2] classify   │   Decides each element's category:
│                 │     SPAN | SUBSTRUCTURE | INTERFACE | WHOLE_BRIDGE
│                 │   via a 4-layer cascade:
│                 │     ① keyword on element name      (primary)
│                 │     ② owner-specific number map     (per-project)
│                 │     ③ AASHTO standard number table  (fast-path)
│                 │     ④ learned rules (low confidence, re-prompt)
│                 │     ⑤ → UNCERTAIN if none match
└─────────────────┘
         │ classified.json + uncertain list
         ▼
┌─────────────────┐
│ [3] review (if  │   Spawns a local HTTP server, opens the browser to a
│   any uncertain)│   review page, you click categories, submit. Decisions
│                 │   are saved to config.yaml (learning over time).
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   [4] regroup   │   Pivots elements onto physical stations in walking
│                 │   order: Abut 1 → Span 1 → Pier 1 → Span 2 → ...
│                 │   Handles label noise: "Sp.1", "Pier 1 (Bent 2)",
│                 │   "Abutment 1 (West)" all canonicalize correctly.
└─────────────────┘
         │ stations.json
         ▼
┌─────────────────┐
│    [5] render   │   Generates the field-ready PDF with reportlab.
│                 │   Each station gets a page with category subsections,
│                 │   color-coded CS highlighting, blank Field Notes lines,
│                 │   and an Inspector signoff line.
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   output.pdf    │
└─────────────────┘
```

### Element categories

The pipeline classifies every element into one of four categories that
control where it appears in the output:

| Category       | Examples                              | Where it appears                                  |
| -------------- | ------------------------------------- | ------------------------------------------------- |
| `SPAN`         | Deck, Girder, Beam, Stringer, Railing | Split across span pages (one row per span)        |
| `SUBSTRUCTURE` | Column, Pier Cap, Abutment, Footing   | On the corresponding Pier/Abutment page           |
| `INTERFACE`    | Bearing, Joint Seal                   | On the Pier/Abutment page they physically sit on  |
| `WHOLE_BRIDGE` | Wearing surface, Paint, Drainage      | Single section at the end (full table preserved)  |

Within each station, elements are grouped into clearly-labeled subsections
so the inspector knows at a glance: "Substructure Elements", "Interface
Elements", "Span Elements".

### Bent / Pier alignment

Many reports use "Bent N" and "Pier N" inconsistently — sometimes for the
same physical thing. The tool handles this via the `bent_pier_alignment`
setting in `config.yaml`:

- `bent_minus_one` (default) — Bent 1 = Abutment 1, Bent 2 = Pier 1, etc.
- `bent_equals_pier` — Bent N = Pier N (no offset)
- `none` — Keep Bent and Pier as separate stations

So `"Pier 1 (Bent 2)"` and `"Bent 2"` (written by different inspectors for
the same physical pier) both end up on the same "Pier 1" page.

---

## Configuration

All configuration lives in two YAML files in the `config/` directory.

### `config/config.yaml` — project-level config (you edit this)

This file persists across runs and **grows over time** as the review UI
learns from your classifications. Example excerpt:

```yaml
owner: "NYSDOT"
bent_pier_alignment: bent_minus_one

# Keyword rules — primary classification mechanism.
# Order matters: more specific terms first.
keyword_rules:
  - keywords: ["pot bearing", "elastomeric bearing", "bearing"]
    exclude_keywords: ["bearing seat"]
    category: INTERFACE
    confidence: high

  - keywords: ["pier cap", "bent cap"]
    category: SUBSTRUCTURE
    confidence: high

  - keywords: ["deck"]
    exclude_keywords: ["deck drain", "deck joint"]
    category: SPAN
    confidence: high
  # ... etc

# Owner-specific number mapping for non-AASHTO numbers
owner_mapping:
  "NY-1010":
    category: SPAN
    name: "NYSDOT Bridge Deck"

# Rules learned from the review UI — low confidence by default
# (re-prompts next time, pre-filled with previous answer).
learned_rules: []

aashto_enabled: true
```

### `config/aashto_defaults.yaml` — built-in AASHTO table (read-only)

Contains the standard AASHTO NBE/BME element numbers and their categories.
You shouldn't need to edit this; it's used as a fast-path lookup when an
element's keyword doesn't match anything.

---

## The interactive review step

When the pipeline encounters an element it can't confidently classify
(e.g., an unusual owner-custom element like "Cathodic Protection System"),
it pauses and opens a review page in your browser:

![Review UI screenshot would go here]

For each unclassified element, you click one of four large buttons:

- **Span** (deck / girder / rail)
- **Substructure** (column / cap / abutment)
- **Interface** (bearing / joint)
- **Whole-Bridge** (paint / drainage / wearing surface)

Optional fields per element:

- **Keyword to learn** — a single word from the element name that should
  match similar elements in the future. The tool auto-suggests a sensible
  one (skipping generic words like "Reinforced", "Concrete", "Steel").
- **Trust this rule permanently** — checkbox. If checked, the learned
  rule is saved as `confidence: high` and will auto-classify next time.
  If unchecked, it's saved as `confidence: low` and re-prompts next time
  (pre-filled with this answer).

Once all elements are classified, you click "Submit & Continue Pipeline".
The browser tab tells you it's safe to close, the local server shuts
itself down, and the pipeline finishes generating the PDF.

### Privacy

The local server only binds to `127.0.0.1` (loopback). No outside
connection, no data leaves your machine.

---

## Handling different report formats

The default extractor expects element headers of the form
`Element <number>: <name>` and tables with columns for Location, CS1, CS2,
CS3, CS4, and Notes. Real-world reports vary:

### Column name variations

The extractor matches columns flexibly:
- `Location` / `Span` / `Pier` / `Bent` for the location column
- `CS1`/`CS 1`/`Good` for CS1 (and similar for CS2-CS4)
- `Notes`/`Remarks`/`Comments` for the notes column

Other column names work as long as they contain one of these substrings.

### Element header variations

The default regex is `Element\s+([\w\-]+)\s*[:\-]\s*([^\n\r]+)`, which
matches "Element 12: name", "Element OW-44 - name", "Element NY-1010: name".

If your report uses a different format like `12 - Reinforced Concrete Deck`,
edit the `ELEMENT_HEADER_RE` regex at the top of `extract.py`.

### Different owner / numbering system

The keyword-matching is owner-agnostic — element names like "deck",
"girder", "column" mean the same thing regardless of who wrote the
report. For owner-specific numbers, populate the `owner_mapping` section
of `config.yaml`. For owner-specific keywords, add new entries to
`keyword_rules`.

### Location label variations

The location-normalizer handles:
- `Span 1` / `Sp. 1` / `Sp 1`
- `Pier 1` / `Pier 1 (Bent 2)` / `Bent 2`
- `Abutment 1` / `Abut. 1` / `Abut 1` / `Abutment 1 (West)`

If your reports use radically different conventions (e.g., station
numbers like `STA 1+50.00`), edit the regexes at the top of `regroup.py`.

---

## Project structure

```
bridge-pipeline/
├── README.md
├── requirements.txt
├── pipeline.py                   # Main entry point
│
├── extract.py                    # Module 1: PDF → element_data.json
├── classify.py                   # Module 2: 4-layer classification cascade
├── review_server.py              # Module 3: local HTTP server for review UI
├── regroup.py                    # Module 4: pivot to physical stations
├── render.py                     # Module 5: generate output PDF
│
├── templates/
│   └── review.html               # Review UI (vanilla JS, no framework)
│
├── config/
│   ├── config.yaml               # Project config (you edit this; grows)
│   └── aashto_defaults.yaml      # Built-in AASHTO element table
│
├── make_sample_input.py          # Generates a synthetic test PDF
└── sample_input.pdf              # Built-in demo input
```

Each module is independently runnable (`python <module>.py`) and writes
its output to a JSON file. This makes debugging straightforward: if
something looks wrong in the final PDF, walk back through the JSON files
to find which stage introduced the issue.

---

## Troubleshooting

### "Extracted 0 elements"

Your element headers don't match the default regex. Open `extract.py`,
find `ELEMENT_HEADER_RE`, and adjust it to match your format. Run
`python extract.py your.pdf` to test in isolation.

### "Some rows are missing from the output"

The extractor uses position-aware table pairing. If a single table spans
multiple pages, both halves should be captured. If you see truncated data:

1. Check `element_data.json` to see what was actually extracted.
2. If the input has rows the extractor missed, your PDF may use embedded
   images instead of real tables — pdfplumber can't read those. You'd
   need OCR (e.g., with `pdf2image` + `pytesseract`) as a preprocessing
   step.

### "Two elements that should be the same pier are on different pages"

Check that `bent_pier_alignment` in `config.yaml` matches your bridge's
convention. Try `bent_equals_pier` if the default `bent_minus_one`
doesn't work.

### Review UI doesn't open in browser

The pipeline uses `webbrowser.open()` which works on most platforms but
can fail in headless environments (containers, SSH sessions, WSL without
a display server). Workarounds:

- Manually open the URL printed in the terminal
  (`http://127.0.0.1:<some-port>/review`)
- Use `--skip-review` and edit `classified.json` by hand, then run the
  later stages manually

### Wrong element category despite keyword match

The keyword rules in `config.yaml` are checked in order; the first match
wins. If `"deck"` matches before `"deck drain"`, add `"deck drain"` to
the `exclude_keywords` of the deck rule, or move a more specific rule
earlier in the list.

---

## Roadmap

Things that would be nice to add (PRs welcome):

- [ ] OCR fallback for scanned PDFs (currently text-only)
- [ ] Support for input formats other than PDF (Excel, CSV exports from
      inspection software)
- [ ] Photo placement — embed referenced photos onto the relevant station
      pages
- [ ] Trends across inspections — diff against last year's report,
      highlight worsening conditions
- [ ] Mobile-friendly output (iPad-sized PDF or HTML version)
- [ ] Better handling of cable-stayed / suspension bridges where cables
      are span-relevant but cross multiple spans

---

## Contributing

Bug reports and PRs welcome. A few guidelines:

- The pipeline is intentionally modular — please keep modules
  independently runnable and avoid cross-module coupling.
- Real-world inspection reports vary wildly. If your fix is "make it work
  for *my* report format", consider whether it should be a config option
  rather than a hard-coded change.
- Sample/synthetic input data for tests should not contain real bridge
  IDs or proprietary owner data.

---

## License

MIT License. See `LICENSE` file.

---

## Acknowledgements

Element categorization defaults are based on the AASHTO Manual for Bridge
Element Inspection (MBEI), 2nd edition. This tool is not affiliated with
or endorsed by AASHTO or FHWA.
