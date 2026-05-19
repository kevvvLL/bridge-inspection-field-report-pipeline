"""
Generate a synthetic element-organized PDF.
Includes some non-standard elements to demonstrate the uncertain/review flow.
"""
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

styles = getSampleStyleSheet()
small = ParagraphStyle('s', parent=styles['BodyText'], fontSize=8, leading=10)

ELEMENTS = [
    # AASHTO standard elements (will fast-path)
    {"elem_no": "12",  "elem_name": "Reinforced Concrete Deck", "unit": "sq.ft.", "total_qty": 24500,
     "rows": [
        ("Span 1",  4800, 100, 0,  0,  "Minor map cracking on underside near west curb."),
        ("Span 2",  4600, 280, 20, 0,  "Efflorescence visible. Three spalling areas ~6\" at midspan."),
        ("Span 3",  4500, 380, 20, 0,  "Heavy efflorescence. Transverse cracks every 8-10 ft."),
        ("Sp. 4",   4700, 200, 0,  0,  "Light scaling on top surface near drains."),
        ("Span 5",  4900, 100, 0,  0,  "Good condition overall."),
     ]},

    {"elem_no": "107", "elem_name": "Steel Open Girder/Beam", "unit": "lin.ft.", "total_qty": 4200,
     "rows": [
        ("Span 1", 820, 30,  0, 0, "Paint intact. Minor surface rust at bearings."),
        ("Span 2", 810, 80,  10, 0, "Section loss G3 bottom flange near Pier 2 — 1/16\" deep over 18\"."),
        ("Span 3", 790, 130, 30, 0, "Pack rust between top flange and deck haunch. Paint peeling G2-G4."),
        ("Span 4", 820, 40,  0,  0, "Minor paint loss at splice plates."),
        ("Span 5", 820, 20,  0,  0, "Good condition."),
     ]},

    {"elem_no": "215", "elem_name": "Reinforced Concrete Abutment", "unit": "lin.ft.", "total_qty": 120,
     "rows": [
        ("Abutment 1 (West)", 50, 8, 2, 0, "Vertical crack at NW corner, ~1/16\" wide, 4 ft tall."),
        ("Abutment 2 (East)", 55, 5, 0, 0, "Light staining. No structural concerns."),
     ]},

    {"elem_no": "205", "elem_name": "Reinforced Concrete Column", "unit": "each", "total_qty": 16,
     "rows": [
        ("Pier 1 (Bent 2)", 4, 0, 0, 0, "Good condition all columns."),
        ("Pier 2 (Bent 3)", 3, 1, 0, 0, "Column C2 has spall at base ~8\"x6\", rebar exposed."),
        ("Pier 3 (Bent 4)", 4, 0, 0, 0, "Good condition."),
        ("Pier 4 (Bent 5)", 3, 1, 0, 0, "Column C4 minor honeycomb at construction joint."),
     ]},

    {"elem_no": "234", "elem_name": "Reinforced Concrete Pier Cap", "unit": "lin.ft.", "total_qty": 240,
     "rows": [
        ("Bent 2", 58, 2,  0, 0, "Minor shrinkage cracks."),
        ("Bent 3", 50, 8,  2, 0, "Diagonal shear crack near south end, ~1/8\" wide. MONITOR."),
        ("Bent 4", 56, 4,  0, 0, "Light efflorescence below bearing seats."),
        ("Bent 5", 55, 5,  0, 0, "Surface scaling on east face."),
     ]},

    {"elem_no": "310", "elem_name": "Elastomeric Bearing", "unit": "each", "total_qty": 24,
     "rows": [
        ("Abutment 1", 4, 0, 0, 0, "Bearings seated correctly. No tearing."),
        ("Pier 1",     3, 1, 0, 0, "Bearing B2-N3 shows slight bulge. Monitor."),
        ("Pier 2",     4, 0, 0, 0, "Good condition."),
        ("Pier 3",     3, 1, 0, 0, "Bearing B4-S1 has minor edge cracking on elastomer."),
        ("Pier 4",     4, 0, 0, 0, "Good condition."),
        ("Abutment 2", 4, 0, 0, 0, "Bearings clean and properly aligned."),
     ]},

    {"elem_no": "300", "elem_name": "Strip Seal Expansion Joint", "unit": "lin.ft.", "total_qty": 180,
     "rows": [
        ("Abutment 1", 30, 0, 0, 0, "Clean, intact."),
        ("Pier 1",     28, 2, 0, 0, "Minor debris accumulation."),
        ("Pier 2",     25, 5, 0, 0, "Seal lifted in 6\" section. Recommend cleaning."),
        ("Pier 3",     28, 2, 0, 0, "OK."),
        ("Pier 4",     30, 0, 0, 0, "Clean."),
        ("Abutment 2", 30, 0, 0, 0, "Clean."),
     ]},

    {"elem_no": "330", "elem_name": "Metal Bridge Railing", "unit": "lin.ft.", "total_qty": 1800,
     "rows": [
        ("Span 1", 350, 10, 0, 0, "Paint intact."),
        ("Span 2", 340, 18, 2, 0, "Impact damage to top rail at midspan, ~3 ft section dented."),
        ("Span 3", 345, 15, 0, 0, "Minor paint loss at posts."),
        ("Span 4", 348, 12, 0, 0, "Good condition."),
        ("Span 5", 350, 10, 0, 0, "Good condition."),
     ]},

    # WHOLE_BRIDGE element - will go in final section
    {"elem_no": "510", "elem_name": "Wearing Surfaces", "unit": "sq.ft.", "total_qty": 24500,
     "rows": [
        ("Span 1", 4700, 200, 0, 0, "Light surface scaling."),
        ("Span 2", 4400, 480, 20, 0, "Pothole patches visible. 2x rutting in WB lane."),
        ("Span 3", 4500, 400, 0, 0, "Surface scaling."),
        ("Span 4", 4700, 200, 0, 0, "Good condition."),
        ("Span 5", 4900, 100, 0, 0, "Good condition."),
     ]},

    # --- NON-STANDARD elements that exercise the review flow ---

    # Custom number not in AASHTO, BUT name has clear keyword (will hit
    # keyword rule "diaphragm"? — actually 'diaphragm' not in our keyword
    # rules so this should go UNCERTAIN)
    {"elem_no": "8001", "elem_name": "Steel Diaphragm", "unit": "each", "total_qty": 40,
     "rows": [
        ("Span 1", 8, 0, 0, 0, "All connections sound."),
        ("Span 2", 7, 1, 0, 0, "One bolt missing at D3."),
        ("Span 3", 8, 0, 0, 0, "Good."),
        ("Span 4", 7, 1, 0, 0, "Loose bolt at D7."),
        ("Span 5", 8, 0, 0, 0, "Good."),
     ]},

    # Owner-custom whole-bridge element, totally unknown
    {"elem_no": "OW-44", "elem_name": "Cathodic Protection System", "unit": "L.S.", "total_qty": 1,
     "rows": [
        ("Whole Bridge", 0, 1, 0, 0, "System operational but anode reading low. Schedule replacement."),
     ]},
]

def build(out_path):
    doc = SimpleDocTemplate(out_path, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)
    story = []
    story.append(Paragraph("BRIDGE INSPECTION REPORT", styles['Heading1']))
    story.append(Paragraph("Bridge No. 12345 — Element-Level Condition Assessment", styles['Heading2']))
    story.append(Paragraph("Inspection Date: 2026-04-15", styles['BodyText']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "This report is organized by element. Each element table lists the condition state "
        "quantities (CS1=Good, CS2=Fair, CS3=Poor, CS4=Severe) for each location/span "
        "along with inspector notes.", styles['BodyText']))
    story.append(PageBreak())

    for el in ELEMENTS:
        story.append(Paragraph(f"Element {el['elem_no']}: {el['elem_name']}", styles['Heading2']))
        story.append(Paragraph(f"Unit: {el['unit']} &nbsp;&nbsp; Total Quantity: {el['total_qty']}", styles['BodyText']))
        story.append(Spacer(1, 6))
        header = ["Location", "CS1", "CS2", "CS3", "CS4", "Notes"]
        data = [header]
        for r in el["rows"]:
            loc, cs1, cs2, cs3, cs4, notes = r
            data.append([loc, str(cs1), str(cs2), str(cs3), str(cs4), Paragraph(notes, small)])
        t = Table(data, colWidths=[1.2*inch, 0.5*inch, 0.5*inch, 0.5*inch, 0.5*inch, 3.6*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
        ]))
        story.append(t)
        story.append(Spacer(1, 16))
    doc.build(story)
    print(f"Created {out_path}")

if __name__ == "__main__":
    build("/home/claude/bridge_pipeline/sample_input.pdf")
