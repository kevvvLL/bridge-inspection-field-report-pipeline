"""
Module 4: REGROUP
=================
Pivots classified elements into physical-station sections in walking order:
  Abut 1 -> Span 1 -> Pier 1 -> Span 2 -> Pier 2 -> ... -> Abut N

Then a final "Whole Bridge" section for display_mode=whole elements.

Per-station, entries are organized by category subsection:
  Span station:    Span elements only
  Pier station:    Substructure + Interface subsections
  Abut station:    Substructure + Interface subsections

Location normalization handles real-world label noise:
  "Span 1", "Sp. 1", "S1"           -> SPAN_1
  "Bent 2", "Pier 1 (Bent 2)"       -> PIER_1   (when alignment=bent_minus_one)
  "Abutment 1 (West)"               -> ABUT_1
"""
import json
import re
import sys
import yaml
from collections import OrderedDict
from pathlib import Path

PIER_RE  = re.compile(r"\bpier\s*(\d+)\b", re.IGNORECASE)
BENT_RE  = re.compile(r"\bbent\s*(\d+)\b", re.IGNORECASE)
SPAN_RE  = re.compile(r"\b(?:span|sp\.?)\s*(\d+)\b", re.IGNORECASE)
ABUT_RE  = re.compile(r"\b(?:abut\.?|abutment)\s*(\d+)?\b", re.IGNORECASE)


def normalize_location(raw: str, bent_pier_alignment: str = "bent_minus_one"
                      ) -> tuple[str, str, int]:
    """Return (canonical_key, display_label, sort_order).

    bent_pier_alignment governs how Bent N maps to Pier:
      'bent_minus_one' -> Bent N = Pier (N-1); so Bent 2 = Pier 1
                          (typical convention: Bent 1 = Abut 1, Bent 2..K = Piers)
      'bent_equals_pier' -> Bent N = Pier N
      'none'             -> keep Bent and Pier as separate stations
    """
    s = (raw or "").strip()
    if not s:
        return ("UNSPECIFIED", "Unspecified", 99_999)

    # Prefer the explicit Pier number if present (handles "Pier 1 (Bent 2)")
    m_pier = PIER_RE.search(s)
    if m_pier:
        n = int(m_pier.group(1))
        return (f"PIER_{n}", f"Pier {n}", 2 * n)

    m_bent = BENT_RE.search(s)
    if m_bent:
        n = int(m_bent.group(1))
        if bent_pier_alignment == "bent_minus_one":
            pier_n = n - 1
            if pier_n <= 0:
                # Bent 1 = Abutment 1
                return (f"ABUT_1", "Abutment 1", 0)
            return (f"PIER_{pier_n}", f"Pier {pier_n}", 2 * pier_n)
        elif bent_pier_alignment == "bent_equals_pier":
            return (f"PIER_{n}", f"Pier {n}", 2 * n)
        else:
            return (f"BENT_{n}", f"Bent {n}", 2 * n)

    m_span = SPAN_RE.search(s)
    if m_span:
        n = int(m_span.group(1))
        return (f"SPAN_{n}", f"Span {n}", 2 * n - 1)

    m_abut = ABUT_RE.search(s)
    if m_abut:
        n = int(m_abut.group(1)) if m_abut.group(1) else 1
        order = 0 if n == 1 else 100_000
        return (f"ABUT_{n}", f"Abutment {n}", order)

    return (f"OTHER_{s}", s, 99_998)


def _entry_from_row(elem: dict, row: dict) -> dict:
    return {
        "elem_no": elem["elem_no"],
        "elem_name": elem["elem_name"],
        "unit": elem["unit"],
        "category": elem["_classification"]["category"],
        "display_mode": elem["_classification"]["display_mode"],
        "location_raw": row["location_raw"],
        "cs1": row["cs1"], "cs2": row["cs2"],
        "cs3": row["cs3"], "cs4": row["cs4"],
        "notes": row["notes"],
    }


def regroup(classified: list[dict],
            bent_pier_alignment: str = "bent_minus_one") -> dict:
    """Pivot classified elements into station-based sections."""
    stations: OrderedDict[str, dict] = OrderedDict()
    whole_bridge: list[dict] = []

    for el in classified:
        cls = el["_classification"]
        if cls["category"] == "UNCERTAIN":
            continue

        if cls["display_mode"] == "whole":
            whole_bridge.append({
                "elem_no": el["elem_no"],
                "elem_name": el["elem_name"],
                "unit": el["unit"],
                "category": cls["category"],
                "rows": el["rows"],
            })
            continue

        for row in el["rows"]:
            key, label, order = normalize_location(
                row["location_raw"], bent_pier_alignment)
            station = stations.get(key)
            if station is None:
                station = {"key": key, "label": label, "sort": order,
                           "subsections": OrderedDict()}
                stations[key] = station
            sub = station["subsections"].setdefault(cls["category"], [])
            sub.append(_entry_from_row(el, row))

    ordered = sorted(stations.values(), key=lambda s: (s["sort"], s["label"]))
    for st in ordered:
        for cat, lst in st["subsections"].items():
            lst.sort(key=lambda e: (int(e["elem_no"])
                                    if str(e["elem_no"]).isdigit() else 9999,
                                    e["elem_name"]))

    return {"stations": ordered, "whole_bridge": whole_bridge}


def main():
    in_path  = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/bridge_pipeline/classified.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/bridge_pipeline/stations.json"
    cfg_path = sys.argv[3] if len(sys.argv) > 3 else "/home/claude/bridge_pipeline/config/config.yaml"

    data = json.loads(Path(in_path).read_text())
    classified = data["classified"]
    cfg = yaml.safe_load(Path(cfg_path).read_text()) or {}
    alignment = cfg.get("bent_pier_alignment", "bent_minus_one")
    result = regroup(classified, bent_pier_alignment=alignment)
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"Built {len(result['stations'])} stations + "
          f"{len(result['whole_bridge'])} whole-bridge elements "
          f"(alignment: {alignment})")
    for st in result["stations"]:
        subs = ", ".join(f"{c}({len(lst)})" for c, lst in st["subsections"].items())
        print(f"  {st['label']:18s} [{subs}]")
    if result["whole_bridge"]:
        print("  Whole Bridge:")
        for w in result["whole_bridge"]:
            print(f"    - {w['elem_no']:>6s}  {w['elem_name']} ({len(w['rows'])} rows)")


if __name__ == "__main__":
    main()
