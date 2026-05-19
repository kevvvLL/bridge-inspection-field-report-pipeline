"""
Module 2: CLASSIFY
==================
4-layer cascade per element:
  ① Keyword rule (high confidence)  ← primary
  ② Owner-specific number mapping
  ③ AASHTO standard number table   ← fast path
  ④ Learned rule (low confidence)  → still goes to UNCERTAIN
                                     (pre-fills user's previous answer)
  → UNCERTAIN if none match

Categories: SPAN | SUBSTRUCTURE | INTERFACE | WHOLE_BRIDGE
display_mode: split (default) | whole
"""
import json
import sys
import yaml
from pathlib import Path

CATEGORIES = ["SPAN", "SUBSTRUCTURE", "INTERFACE", "WHOLE_BRIDGE"]
DEFAULT_DISPLAY_MODE = {
    "SPAN": "split", "SUBSTRUCTURE": "split",
    "INTERFACE": "split", "WHOLE_BRIDGE": "whole",
}


def load_config(config_path: str, aashto_path: str) -> dict:
    cfg = yaml.safe_load(Path(config_path).read_text())
    aashto = {}
    if cfg.get("aashto_enabled", True):
        aashto_doc = yaml.safe_load(Path(aashto_path).read_text())
        aashto = aashto_doc.get("aashto_table", {})
    cfg["_aashto"] = aashto
    return cfg


def _match_keyword_rule(name: str, rules: list[dict]) -> dict | None:
    name_lc = (name or "").lower()
    for rule in rules:
        kws = [k.lower() for k in rule.get("keywords", [])]
        excludes = [k.lower() for k in rule.get("exclude_keywords", [])]
        if any(e in name_lc for e in excludes):
            continue
        if any(k in name_lc for k in kws):
            return rule
    return None


def classify_one(elem_no, elem_name: str, cfg: dict) -> dict:
    """
    Returns {
      "category": "...", "display_mode": "...",
      "source": "keyword|owner|aashto|learned|uncertain",
      "reason": "...",
      "prefilled": {category, display_mode}  # only when source=learned
    }
    """
    name = elem_name or ""

    # ① keyword rules (high confidence)
    rule = _match_keyword_rule(name, cfg.get("keyword_rules") or [])
    if rule and rule.get("confidence", "high") == "high":
        cat = rule["category"]
        dm = rule.get("display_mode", DEFAULT_DISPLAY_MODE[cat])
        kw_hit = next((k for k in rule["keywords"] if k.lower() in name.lower()), "")
        return {"category": cat, "display_mode": dm, "source": "keyword",
                "reason": f"keyword '{kw_hit}'"}

    # ② owner mapping
    owner_map = cfg.get("owner_mapping") or {}
    key = str(elem_no)
    if key in owner_map:
        m = owner_map[key]
        cat = m["category"]
        dm = m.get("display_mode", DEFAULT_DISPLAY_MODE[cat])
        return {"category": cat, "display_mode": dm, "source": "owner",
                "reason": f"owner_mapping[{key}]"}

    # ③ AASHTO
    aashto = cfg.get("_aashto") or {}
    try:
        n = int(str(elem_no).strip())
        if n in aashto:
            m = aashto[n]
            cat = m["category"]
            dm = m.get("display_mode", DEFAULT_DISPLAY_MODE[cat])
            return {"category": cat, "display_mode": dm, "source": "aashto",
                    "reason": f"AASHTO #{n}"}
    except (ValueError, TypeError):
        pass

    # ④ learned rules — match but route to uncertain with pre-fill
    learned_match = _match_keyword_rule(name, cfg.get("learned_rules") or [])
    if learned_match:
        cat = learned_match["category"]
        dm = learned_match.get("display_mode", DEFAULT_DISPLAY_MODE[cat])
        return {"category": "UNCERTAIN", "display_mode": None,
                "source": "learned", "reason": "matched a learned rule",
                "prefilled": {"category": cat, "display_mode": dm}}

    return {"category": "UNCERTAIN", "display_mode": None,
            "source": "uncertain", "reason": "no rule matched"}


def classify_all(elements: list[dict], cfg: dict) -> tuple[list[dict], list[dict]]:
    """Returns (classified_elements, uncertain_list)."""
    classified = []
    uncertain = []
    for el in elements:
        verdict = classify_one(el["elem_no"], el["elem_name"], cfg)
        record = {**el, "_classification": verdict}
        classified.append(record)
        if verdict["category"] == "UNCERTAIN":
            uncertain.append({
                "elem_no": el["elem_no"],
                "elem_name": el["elem_name"],
                "unit": el["unit"],
                "row_count": len(el["rows"]),
                "sample_locations": [r["location_raw"] for r in el["rows"][:3]],
                "prefilled": verdict.get("prefilled"),
                "reason": verdict["reason"],
            })
    return classified, uncertain


def apply_decisions(classified: list[dict], decisions: dict[str, dict]) -> list[dict]:
    """Apply user decisions to UNCERTAIN elements; mutates and returns the list."""
    for rec in classified:
        if rec["_classification"]["category"] != "UNCERTAIN":
            continue
        d = decisions.get(str(rec["elem_no"]))
        if not d: continue
        cat = d["category"]
        dm = d.get("display_mode", DEFAULT_DISPLAY_MODE[cat])
        rec["_classification"] = {
            "category": cat, "display_mode": dm,
            "source": "user", "reason": "from review UI",
        }
    return classified


def main():
    cfg_path     = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/bridge_pipeline/config/config.yaml"
    aashto_path  = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/bridge_pipeline/config/aashto_defaults.yaml"
    in_path      = sys.argv[3] if len(sys.argv) > 3 else "/home/claude/bridge_pipeline/element_data.json"
    out_path     = sys.argv[4] if len(sys.argv) > 4 else "/home/claude/bridge_pipeline/classified.json"

    cfg = load_config(cfg_path, aashto_path)
    elements = json.loads(Path(in_path).read_text())
    classified, uncertain = classify_all(elements, cfg)
    Path(out_path).write_text(json.dumps(
        {"classified": classified, "uncertain": uncertain},
        indent=2, ensure_ascii=False))
    print(f"Classified {len(classified)} elements; {len(uncertain)} uncertain.")
    for u in uncertain:
        prefill = f" (prefill: {u['prefilled']['category']})" if u["prefilled"] else ""
        print(f"  ? {u['elem_no']:>6s}  {u['elem_name']}{prefill}")


if __name__ == "__main__":
    main()
