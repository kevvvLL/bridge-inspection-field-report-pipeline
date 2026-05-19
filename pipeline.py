"""
Bridge Inspection Report Reorganizer — End-to-End Pipeline
==========================================================
Usage:
  python pipeline.py <input.pdf> [output.pdf]

Stages:
  [1] extract         PDF tables   -> element_data.json
  [2] classify        elements     -> classified.json + uncertain list
  [3] review (if any) browser UI   -> user decisions (also updates config.yaml)
  [4] regroup         classified   -> stations.json
  [5] render          stations     -> field_report.pdf
"""
import json
import sys
from pathlib import Path

from extract import extract
from classify import load_config, classify_all, apply_decisions
from review_server import run_review
from regroup import regroup
from render import render

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "config" / "config.yaml"
AASHTO_PATH = HERE / "config" / "aashto_defaults.yaml"
TEMPLATE_PATH = HERE / "templates" / "review.html"


def run(input_pdf: str, output_pdf: str, work_dir: Path | None = None,
        skip_review: bool = False):
    work = work_dir or HERE
    work.mkdir(parents=True, exist_ok=True)

    # -- 1. Extract --
    print(f"[1/5] Extracting element tables from {input_pdf}")
    elements = extract(input_pdf)
    total_rows = sum(len(e["rows"]) for e in elements)
    print(f"      -> {len(elements)} elements, {total_rows} location-rows")
    (work / "element_data.json").write_text(
        json.dumps(elements, indent=2, ensure_ascii=False))

    # -- 2. Classify --
    print(f"[2/5] Classifying elements (4-layer cascade)")
    cfg = load_config(str(CONFIG_PATH), str(AASHTO_PATH))
    classified, uncertain = classify_all(elements, cfg)

    auto_count = len(classified) - len(uncertain)
    print(f"      -> {auto_count} auto-classified, {len(uncertain)} need review")
    for el in classified:
        c = el["_classification"]
        if c["category"] != "UNCERTAIN":
            print(f"         ✓ {el['elem_no']:>6s}  {el['elem_name']:<40s}"
                  f" -> {c['category']:<13s} [{c['source']}]")
        else:
            prefill = ""
            if c.get("prefilled"):
                prefill = f" (prefill: {c['prefilled']['category']})"
            print(f"         ? {el['elem_no']:>6s}  {el['elem_name']:<40s}"
                  f" -> UNCERTAIN{prefill}")

    # -- 3. Review (if needed) --
    if uncertain and not skip_review:
        print(f"[3/5] Launching review UI for {len(uncertain)} uncertain element(s)")
        decisions = run_review(
            uncertain, str(TEMPLATE_PATH), config_path=str(CONFIG_PATH))
        classified = apply_decisions(classified, decisions)
    elif uncertain and skip_review:
        print(f"[3/5] SKIPPED ({len(uncertain)} uncertain elements left unclassified)")
    else:
        print(f"[3/5] No review needed — all auto-classified.")

    (work / "classified.json").write_text(json.dumps(
        {"classified": classified, "uncertain": uncertain},
        indent=2, ensure_ascii=False))

    # -- 4. Regroup --
    print(f"[4/5] Regrouping by physical station")
    alignment = cfg.get("bent_pier_alignment", "bent_minus_one")
    data = regroup(classified, bent_pier_alignment=alignment)
    print(f"      -> {len(data['stations'])} stations + "
          f"{len(data['whole_bridge'])} whole-bridge elements "
          f"(alignment: {alignment})")
    (work / "stations.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False))

    # -- 5. Render --
    print(f"[5/5] Rendering field-ready PDF")
    render(data, output_pdf)
    print(f"      -> {output_pdf}")


def main():
    skip = "--skip-review" in sys.argv
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not positional:
        in_pdf = str(HERE / "sample_input.pdf")
        out_pdf = str(HERE / "field_report.pdf")
    else:
        in_pdf = positional[0]
        out_pdf = positional[1] if len(positional) > 1 else "field_report.pdf"
    run(in_pdf, out_pdf, skip_review=skip)


if __name__ == "__main__":
    main()
