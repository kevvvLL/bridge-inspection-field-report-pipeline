"""
Module 1: EXTRACT  (position-aware version)
===========================================
Header-table pairing is done by Y-COORDINATE on each page, not by appearance
order — handles the common case where pdfplumber under- or over-counts
tables on a page.
"""
import json
import re
import sys
from pathlib import Path
import pdfplumber

ELEMENT_HEADER_RE = re.compile(
    r"Element\s+([\w\-]+)\s*[:\-]\s*([^\n\r]+)", re.IGNORECASE)
UNIT_QTY_RE = re.compile(
    r"Unit:\s*(\S+).*?Total Quantity:\s*([\d,]+)", re.IGNORECASE | re.DOTALL)


def _to_int(x):
    if x is None: return 0
    s = str(x).strip().replace(",", "")
    if not s: return 0
    try: return int(s)
    except ValueError:
        try: return int(float(s))
        except ValueError: return 0


def _find_headers_with_position(page) -> list[dict]:
    """Return headers with their y-coordinate on the page."""
    headers = []
    words = page.extract_words() or []
    full_text = page.extract_text() or ""

    # Find "Element" word occurrences with positions
    element_word_positions = [w for w in words if w["text"].strip() == "Element"]

    for idx, m in enumerate(ELEMENT_HEADER_RE.finditer(full_text)):
        elem_no = m.group(1).strip()
        elem_name = m.group(2).strip()

        # The Nth match in the text corresponds to the Nth "Element" word
        y_top = element_word_positions[idx]["top"] if idx < len(element_word_positions) else 0.0

        tail = full_text[m.end(): m.end() + 200]
        uq = UNIT_QTY_RE.search(tail)
        headers.append({
            "elem_no": elem_no,
            "elem_name": elem_name,
            "unit": uq.group(1) if uq else "",
            "total_qty": _to_int(uq.group(2)) if uq else 0,
            "y_top": y_top,
        })
    return headers


def _find_tables_with_position(page) -> list[dict]:
    out = []
    for tbl in page.find_tables() or []:
        rows = tbl.extract()
        if not rows: continue
        out.append({"rows": rows, "y_top": tbl.bbox[1]})
    return out


def _pair_headers_tables(headers, tables, pending):
    """Pair each table with the nearest preceding header by y."""
    headers_sorted = sorted(headers, key=lambda h: h["y_top"])
    tables_sorted  = sorted(tables, key=lambda t: t["y_top"])
    pairs = []
    for tbl in tables_sorted:
        cands = [h for h in headers_sorted if h["y_top"] < tbl["y_top"]]
        pairs.append((cands[-1] if cands else None, tbl["rows"]))
    new_pending = headers_sorted[-1] if headers_sorted else pending
    return pairs, new_pending


def extract(pdf_path: str) -> list[dict]:
    elements: list[dict] = []
    elem_by_key: dict[str, dict] = {}
    pending = None  # last header from PREVIOUS page

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            headers = _find_headers_with_position(page)
            for h in headers:
                if h["elem_no"] not in elem_by_key:
                    rec = {
                        "elem_no": h["elem_no"],
                        "elem_name": h["elem_name"],
                        "unit": h["unit"],
                        "total_qty": h["total_qty"],
                        "rows": [],
                    }
                    elements.append(rec)
                    elem_by_key[h["elem_no"]] = rec

            tables = _find_tables_with_position(page)
            # Pair using the OLD pending (from previous page) for any
            # tables that appear before this page's first header.
            prev_pending = pending
            pairs, _new_last = _pair_headers_tables(headers, tables, prev_pending)

            for owner, rows in pairs:
                if owner is None:
                    # Continuation table for previous page's last header
                    if prev_pending and prev_pending["elem_no"] in elem_by_key:
                        _ingest_table(elem_by_key[prev_pending["elem_no"]],
                                      rows, skip_header=False)
                else:
                    target = elem_by_key.get(owner["elem_no"])
                    if target is not None:
                        _ingest_table(target, rows)

            # Now update pending to be the last header of THIS page
            # (only if this page had any headers)
            if headers:
                pending = sorted(headers, key=lambda h: h["y_top"])[-1]
    return elements


def _ingest_table(elem: dict, tbl, skip_header: bool = False):
    if not tbl: return
    if not skip_header:
        if len(tbl) < 2: return
        header = [(c or "").strip().lower() for c in tbl[0]]
        data_rows = tbl[1:]
    else:
        first = [(c or "").strip().lower() for c in tbl[0]]
        if any("cs" in c or "location" in c for c in first):
            header = first
            data_rows = tbl[1:]
        else:
            header = ["location", "cs1", "cs2", "cs3", "cs4", "notes"]
            data_rows = tbl

    def col(name_options):
        for i, h in enumerate(header):
            for opt in name_options:
                if opt in h: return i
        return None

    loc_i   = col(["location", "span", "pier", "bent"])
    cs1_i   = col(["cs1", "cs 1", "good"])
    cs2_i   = col(["cs2", "cs 2", "fair"])
    cs3_i   = col(["cs3", "cs 3", "poor"])
    cs4_i   = col(["cs4", "cs 4", "severe"])
    notes_i = col(["notes", "remark", "comment"])

    if loc_i is None: return

    for row in data_rows:
        if not row or all((c is None or str(c).strip() == "") for c in row):
            continue
        loc = (row[loc_i] or "").strip() if loc_i is not None else ""
        if not loc: continue
        if loc.lower() in ("location", "loc"): continue
        elem["rows"].append({
            "location_raw": loc,
            "cs1":   _to_int(row[cs1_i])   if cs1_i   is not None else 0,
            "cs2":   _to_int(row[cs2_i])   if cs2_i   is not None else 0,
            "cs3":   _to_int(row[cs3_i])   if cs3_i   is not None else 0,
            "cs4":   _to_int(row[cs4_i])   if cs4_i   is not None else 0,
            "notes": (row[notes_i] or "").strip() if notes_i is not None else "",
        })


def main():
    in_path  = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/bridge_pipeline/sample_input.pdf"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/bridge_pipeline/element_data.json"
    data = extract(in_path)
    Path(out_path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    total = sum(len(e["rows"]) for e in data)
    print(f"Extracted {len(data)} elements, {total} rows -> {out_path}")
    for el in data:
        print(f"  {el['elem_no']:>6s}  {el['elem_name']:<42s} {len(el['rows'])} rows")


if __name__ == "__main__":
    main()
