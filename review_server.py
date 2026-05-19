"""
Module 3: REVIEW SERVER
=======================
Minimal local HTTP server (stdlib only) for the half-interactive review step.

Flow:
  1. Caller passes the uncertain element list.
  2. Server picks a free port on 127.0.0.1, serves review.html with the data
     injected, and auto-opens the browser.
  3. User fills out the form, clicks Submit -> POST /submit.
  4. Server records the decisions, optionally writes learned rules back into
     config.yaml, sends 200 OK, and shuts itself down.
  5. Function returns the decisions dict.
"""
import http.server
import json
import socket
import socketserver
import threading
import webbrowser
import yaml
from pathlib import Path

DEFAULT_DISPLAY_MODE = {
    "SPAN": "split", "SUBSTRUCTURE": "split",
    "INTERFACE": "split", "WHOLE_BRIDGE": "whole",
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_handler(html_body: str, decisions_holder: dict, shutdown_event):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args, **kwargs):
            return  # silence default logging

        def do_GET(self):
            if self.path in ("/", "/review", "/review.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_body.encode("utf-8"))
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/submit":
                length = int(self.headers.get("Content-Length", 0))
                payload = self.rfile.read(length).decode("utf-8")
                try:
                    decisions_holder["data"] = json.loads(payload)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                except Exception as e:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(str(e).encode())
                # Schedule shutdown after sending the response
                threading.Thread(target=shutdown_event.set, daemon=True).start()
            else:
                self.send_error(404)
    return Handler


def run_review(uncertain: list[dict], template_path: str,
               config_path: str | None = None,
               open_browser: bool = True) -> dict:
    """
    Block until the user submits decisions in the browser. Returns:
        {elem_no_str: {"category": ..., "display_mode": ...}, ...}

    Side effect: appends learned rules to config_path (if provided).
    """
    template = Path(template_path).read_text()
    html = template.replace("__UNCERTAIN_JSON__",
                            json.dumps(uncertain, ensure_ascii=False))

    decisions_holder = {"data": None}
    shutdown_event = threading.Event()
    port = _free_port()
    Handler = _build_handler(html, decisions_holder, shutdown_event)

    httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
    httpd.timeout = 0.3

    url = f"http://127.0.0.1:{port}/review"
    print(f"\n[review] Opening browser at {url}")
    print(f"[review] Waiting for you to submit decisions ...")

    if open_browser:
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    try:
        while not shutdown_event.is_set():
            httpd.handle_request()
    finally:
        httpd.server_close()

    decisions = decisions_holder["data"] or {}
    print(f"[review] Received {len(decisions)} decision(s).")

    # Persist learned rules into config if a path was given
    if config_path and decisions:
        _persist_learned_rules(config_path, uncertain, decisions)

    # Strip out UI-only fields and return a clean structure
    clean = {}
    for k, v in decisions.items():
        cat = v["category"]
        dm = v.get("display_mode") or DEFAULT_DISPLAY_MODE.get(cat, "split")
        clean[k] = {"category": cat, "display_mode": dm}
    return clean


def _persist_learned_rules(config_path: str, uncertain: list[dict],
                           decisions: dict):
    """Append rules to config.yaml. If user clicked 'trust', adds to
    keyword_rules (high confidence). Otherwise adds to learned_rules (low)."""
    cfg = yaml.safe_load(Path(config_path).read_text()) or {}
    cfg.setdefault("keyword_rules", [])
    cfg.setdefault("learned_rules", [])

    elem_lookup = {str(u["elem_no"]): u for u in uncertain}

    for elem_no_str, decision in decisions.items():
        u = elem_lookup.get(elem_no_str)
        if not u: continue
        kw = (decision.get("keyword_hint") or "").strip().lower()
        if not kw: continue

        rule = {
            "keywords": [kw],
            "category": decision["category"],
            "_learned_from": f"{u['elem_name']} (#{elem_no_str})",
        }
        if decision.get("display_mode"):
            rule["display_mode"] = decision["display_mode"]

        if decision.get("trust"):
            rule["confidence"] = "high"
            cfg["keyword_rules"].append(rule)
        else:
            rule["confidence"] = "low"
            cfg["learned_rules"].append(rule)

    Path(config_path).write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    print(f"[review] Updated config: {config_path}")


if __name__ == "__main__":
    # Demo: run with two fake uncertain elements
    demo = [
        {"elem_no": "8001", "elem_name": "Steel Diaphragm", "unit": "each",
         "row_count": 5, "sample_locations": ["Span 1", "Span 2", "Span 3"],
         "prefilled": None, "reason": "no rule matched"},
        {"elem_no": "OW-44", "elem_name": "Cathodic Protection System",
         "unit": "L.S.", "row_count": 1, "sample_locations": ["Whole Bridge"],
         "prefilled": None, "reason": "no rule matched"},
    ]
    result = run_review(demo, "/home/claude/bridge_pipeline/templates/review.html")
    print("Result:", json.dumps(result, indent=2))
