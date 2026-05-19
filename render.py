"""
Module 5: RENDER
================
Produces a field-ready PDF organized by physical station with category
subsections inside each station. Whole-bridge elements get their own
section at the end.

Layout per station:
  [Big station header]
  [Summary line: N elements | Worst CS]
  [Subsection: Span Elements]    (if present)
     [Table: Element | CS1..4 | Notes]
  [Subsection: Substructure Elements]
     [Table]
  [Subsection: Interface Elements]
     [Table]
  [Field Notes blank lines]
  [Signoff line]

Whole-bridge section:
  One sub-block per whole-bridge element, full location-by-location table.
"""
import json
import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER

styles = getSampleStyleSheet()
section_h = ParagraphStyle(
    'SectionH', parent=styles['Heading1'], fontSize=20, leading=24,
    textColor=colors.white, backColor=colors.HexColor('#1f4e79'),
    borderPadding=8, alignment=TA_CENTER, spaceAfter=4,
)
subhead = ParagraphStyle(
    'Subhead', parent=styles['BodyText'], fontSize=9, leading=11,
    textColor=colors.HexColor('#555555'), spaceAfter=8,
)
category_label = ParagraphStyle(
    'CatLabel', parent=styles['BodyText'], fontSize=11, leading=13,
    fontName='Helvetica-Bold', textColor=colors.HexColor('#1f4e79'),
    spaceBefore=10, spaceAfter=4,
)
elem_name_style = ParagraphStyle(
    'ElemName', parent=styles['BodyText'], fontSize=9, leading=11,
    fontName='Helvetica-Bold',
)
notes_style = ParagraphStyle(
    'Notes', parent=styles['BodyText'], fontSize=8.5, leading=10.5,
)
field_label = ParagraphStyle(
    'FieldLabel', parent=styles['BodyText'], fontSize=9, leading=11,
    fontName='Helvetica-Bold', textColor=colors.HexColor('#1f4e79'),
    spaceBefore=10, spaceAfter=4,
)

# Category color theming (matches HTML review UI for consistency)
CATEGORY_BAR_COLOR = {
    "SPAN":         colors.HexColor('#2563eb'),
    "SUBSTRUCTURE": colors.HexColor('#b45309'),
    "INTERFACE":    colors.HexColor('#7c3aed'),
    "WHOLE_BRIDGE": colors.HexColor('#16a34a'),
}
CATEGORY_PRETTY = {
    "SPAN":         "Span Elements",
    "SUBSTRUCTURE": "Substructure Elements",
    "INTERFACE":    "Interface Elements (bearings, joints)",
    "WHOLE_BRIDGE": "Whole-Bridge Elements",
}
# Display order within a station
CATEGORY_ORDER = ["SPAN", "SUBSTRUCTURE", "INTERFACE"]

CS_TINT = {
    1: colors.HexColor('#d4edda'),
    2: colors.HexColor('#fff3cd'),
    3: colors.HexColor('#ffe0b3'),
    4: colors.HexColor('#f8d7da'),
}


def worst_cs(entry):
    if entry["cs4"] > 0: return 4
    if entry["cs3"] > 0: return 3
    if entry["cs2"] > 0: return 2
    return 1


def _build_elem_table(entries: list[dict]) -> Table:
    head = ["Element", "CS1", "CS2", "CS3", "CS4", "Notes"]
    rows = [head]
    worst_levels = []
    for e in entries:
        elem_cell = Paragraph(
            f"<b>{e['elem_no']}</b> &mdash; {e['elem_name']}<br/>"
            f"<font size='7' color='#777'>as recorded: {e['location_raw']} "
            f"&middot; unit: {e['unit']}</font>",
            elem_name_style,
        )
        rows.append([
            elem_cell,
            str(e["cs1"]) if e["cs1"] else "",
            str(e["cs2"]) if e["cs2"] else "",
            str(e["cs3"]) if e["cs3"] else "",
            str(e["cs4"]) if e["cs4"] else "",
            Paragraph(e["notes"] or "&mdash;", notes_style),
        ])
        worst_levels.append(worst_cs(e))

    t = Table(rows, colWidths=[2.1*inch, 0.45*inch, 0.45*inch, 0.45*inch,
                               0.45*inch, 3.6*inch], repeatRows=1)
    ts = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f4e79')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN',      (1,0), (4,-1), 'CENTER'),
        ('VALIGN',     (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.4, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ])
    for i, level in enumerate(worst_levels, start=1):
        ts.add('BACKGROUND', (level, i), (level, i), CS_TINT[level])
    t.setStyle(ts)
    return t


def _build_whole_element_table(rows: list[dict]) -> Table:
    head = ["Location", "CS1", "CS2", "CS3", "CS4", "Notes"]
    data = [head]
    worst_levels = []
    for r in rows:
        # mimic the entry shape for worst_cs
        worst_levels.append(worst_cs(r))
        data.append([
            r["location_raw"],
            str(r["cs1"]) if r["cs1"] else "",
            str(r["cs2"]) if r["cs2"] else "",
            str(r["cs3"]) if r["cs3"] else "",
            str(r["cs4"]) if r["cs4"] else "",
            Paragraph(r["notes"] or "&mdash;", notes_style),
        ])
    t = Table(data, colWidths=[1.3*inch, 0.45*inch, 0.45*inch, 0.45*inch,
                               0.45*inch, 4.4*inch], repeatRows=1)
    ts = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#16a34a')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN',      (1,0), (4,-1), 'CENTER'),
        ('VALIGN',     (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.4, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ])
    for i, level in enumerate(worst_levels, start=1):
        ts.add('BACKGROUND', (level, i), (level, i), CS_TINT[level])
    t.setStyle(ts)
    return t


def _station_worst(station: dict) -> int:
    w = 1
    for entries in station["subsections"].values():
        for e in entries:
            w = max(w, worst_cs(e))
    return w


def _signoff():
    return Paragraph(
        "Inspector initials: ______ &nbsp;&nbsp;&nbsp; "
        "Date/time: _______________ &nbsp;&nbsp;&nbsp; "
        "Photos taken: &#9744; &nbsp;&nbsp; Action required: &#9744;",
        styles['BodyText'])


def _field_notes(lines: int = 5):
    blanks = []
    for _ in range(lines):
        blanks.append(Paragraph("_" * 110,
            ParagraphStyle('blank', parent=styles['BodyText'],
                           fontSize=10, leading=18, textColor=colors.grey)))
    return blanks


def render(data: dict, out_path: str, bridge_title: str = "Bridge No. 12345"):
    stations = data["stations"]
    whole_bridge = data["whole_bridge"]

    doc = SimpleDocTemplate(
        out_path, pagesize=letter,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.5*inch, bottomMargin=0.5*inch,
    )
    story = []

    # ---- Cover + TOC ----
    story.append(Paragraph(bridge_title, styles['Title']))
    story.append(Paragraph(
        "Field Inspection Report — Organized by Walking Station",
        styles['Heading3']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "This report reorganizes the element-level condition data by physical "
        "station along the bridge. Each station page contains all elements "
        "the inspector should examine at that location, grouped into category "
        "subsections. Whole-bridge elements appear in a separate section at "
        "the end.", styles['BodyText']))
    story.append(Spacer(1, 14))
    story.append(Paragraph("<b>Contents</b>", styles['Heading4']))

    toc_data = [["#", "Station", "Categories", "Worst CS"]]
    for i, st in enumerate(stations, 1):
        cats = ", ".join(c.title() for c in st["subsections"].keys())
        toc_data.append([str(i), st["label"], cats, f"CS{_station_worst(st)}"])
    if whole_bridge:
        toc_data.append([str(len(stations) + 1), "Whole-Bridge Elements",
                         f"{len(whole_bridge)} elem(s)",
                         f"CS{max((worst_cs(r) for w in whole_bridge for r in w['rows']), default=1)}"])
    toc = Table(toc_data, colWidths=[0.4*inch, 1.7*inch, 3.0*inch, 0.9*inch])
    toc.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f4e79')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.4, colors.grey),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (3,0), (3,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    story.append(toc)
    story.append(PageBreak())

    # ---- Station pages ----
    for st in stations:
        worst = _station_worst(st)
        total = sum(len(lst) for lst in st["subsections"].values())
        story.append(Paragraph(st["label"].upper(), section_h))
        story.append(Paragraph(
            f"{total} element entr(ies) at this station &nbsp;|&nbsp; "
            f"Worst condition: CS{worst}",
            subhead))

        for cat in CATEGORY_ORDER:
            entries = st["subsections"].get(cat)
            if not entries: continue
            # Category label with colored bullet
            bar = CATEGORY_BAR_COLOR.get(cat, colors.black).hexval()
            story.append(Paragraph(
                f"<font color='{bar}'>&#9632;</font> "
                f"{CATEGORY_PRETTY[cat]}", category_label))
            story.append(_build_elem_table(entries))

        story.append(Paragraph("Field Notes / Observations:", field_label))
        for line in _field_notes(5): story.append(line)
        story.append(Spacer(1, 6))
        story.append(_signoff())
        story.append(PageBreak())

    # ---- Whole-bridge section ----
    if whole_bridge:
        story.append(Paragraph("WHOLE-BRIDGE ELEMENTS", section_h))
        story.append(Paragraph(
            "These elements span the entire structure or aren't tied to a "
            "specific station. Inspect alongside the station-by-station walk.",
            subhead))
        for w in whole_bridge:
            story.append(Paragraph(
                f"<font color='#16a34a'>&#9632;</font> "
                f"<b>{w['elem_no']}</b> &mdash; {w['elem_name']} "
                f"<font size='8' color='#777'>(unit: {w['unit']})</font>",
                category_label))
            story.append(_build_whole_element_table(w["rows"]))
            story.append(Spacer(1, 4))
            for line in _field_notes(3): story.append(line)
            story.append(Spacer(1, 6))

    # Strip trailing page break if any
    while story and isinstance(story[-1], PageBreak):
        story.pop()

    doc.build(story)
    print(f"Wrote {out_path}")


def main():
    in_path  = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/bridge_pipeline/stations.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/bridge_pipeline/field_report.pdf"
    data = json.loads(Path(in_path).read_text())
    render(data, out_path)


if __name__ == "__main__":
    main()
