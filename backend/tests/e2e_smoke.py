"""E2E smoke test for the PIE vertical slice (§20 milestone).

Walks the entire user journey:
  open UI → enter decision → watch real SSE events draw branches →
  select a node → inspect → expand → what-if fork (original preserved).

Screenshots land in docs/screenshots/.
"""

from __future__ import annotations

import pathlib
import sys
import time

from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:5173"
SHOTS = pathlib.Path(__file__).resolve().parents[2] / "docs" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

def main() -> int:
    failures: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 950})
        page.goto(BASE, wait_until="networkidle")
        page.screenshot(path=str(SHOTS / "01-landing.png"))
        print("✓ landing page loaded")

        # 1-3. Enter a decision and submit
        page.click("text=Server migration")
        page.click("text=Explore possibilities")
        page.wait_for_selector(".pie-node.root", timeout=10_000)
        print("✓ root node activated from real backend event")
        page.screenshot(path=str(SHOTS / "02-root-activated.png"))

        # 4-5. Watch branches appear from SSE events
        deadline = time.time() + 30
        while time.time() < deadline:
            count = page.locator(".pie-node").count()
            if count >= 6:
                break
            page.wait_for_timeout(400)
        count = page.locator(".pie-node").count()
        if count < 6:
            failures.append(f"expected ≥6 nodes from discovery, got {count}")
        else:
            print(f"✓ {count} scenario nodes rendered from live events")
        page.wait_for_timeout(2500)  # let pulses settle / completion arrive
        page.screenshot(path=str(SHOTS / "03-explored-graph.png"))

        # 6-7. Select a branch and inspect it
        target = page.locator(".pie-node", has_text="Cutover overruns").first
        target.click()
        expect(page.locator(".inspector h2")).to_contain_text("Cutover", timeout=5_000)
        expect(page.locator(".prob-panel")).to_be_visible()
        print("✓ branch inspector opened with probability panel")
        page.screenshot(path=str(SHOTS / "04-inspector.png"))

        # 8. Expand the branch → depth-2 nodes arrive over SSE
        page.click("text=Expand branch")
        deadline = time.time() + 30
        while time.time() < deadline:
            if page.locator(".depth-badge", has_text="d2").count() >= 2:
                break
            page.wait_for_timeout(400)
        d2 = page.locator(".depth-badge", has_text="d2").count()
        if d2 < 2:
            failures.append(f"expand produced insufficient d2 nodes ({d2})")
        else:
            print(f"✓ branch expanded: {d2} depth-2 nodes from backend events")
        page.screenshot(path=str(SHOTS / "05-expanded.png"))

        # 9-10. What-if fork without destroying the original
        before_titles = page.locator(".pie-node-title").all_inner_texts()
        page.click("text=What-if")
        page.fill(".whatif-form textarea", "We run a parallel canary for 2 weeks before full cutover")
        page.click("text=Fork alternative scenario")
        deadline = time.time() + 20
        while time.time() < deadline:
            if page.locator(".pie-node.alternative").count() >= 1:
                break
            page.wait_for_timeout(400)
        alt_count = page.locator(".pie-node.alternative").count()
        if alt_count < 1:
            failures.append("what-if alternative node did not appear")
        else:
            print("✓ what-if alternative forked and visible")

        # §20 item 10: "generate an alternative scenario without destroying the
        # original analysis" — assert against the authoritative server graph.
        import json as _json
        import urllib.request as _url

        analyses = _json.load(_url.urlopen("http://127.0.0.1:8000/v1/analyses"))
        latest_id = analyses[0]["id"]
        # The client sees the alternative the moment the SSE discovery event
        # lands; the backend adds the MODIFIES back-edge right after — poll
        # until the authoritative graph shows the full linkage.
        snap: dict = {}
        alt_nodes: list = []
        mod_edges: list = []
        alt_edges: list = []
        link_deadline = time.time() + 8
        while time.time() < link_deadline:
            snap = _json.load(
                _url.urlopen(f"http://127.0.0.1:8000/v1/analyses/{latest_id}/graph")
            )
            server_nodes = snap["graph"]["nodes"]
            alt_nodes = [n for n in server_nodes.values() if n["status"] == "alternative"]
            mod_edges = [
                e for e in snap["graph"]["edges"] if e["relationship"] == "MODIFIES"
            ]
            alt_edges = [
                e for e in snap["graph"]["edges"] if e["relationship"] == "ALTERNATIVE_TO"
            ]
            if alt_nodes and mod_edges and alt_edges:
                break
            time.sleep(0.3)
        server_nodes = snap["graph"]["nodes"]
        server_titles = {n["title"] for n in server_nodes.values()}
        missing = [t for t in before_titles if t not in server_titles]
        if missing:
            failures.append(f"original scenarios destroyed by what-if: {missing}")
        elif not alt_nodes or not mod_edges or not alt_edges:
            failures.append(
                f"alternative linkage incomplete (alt={len(alt_nodes)}, "
                f"MODIFIES={len(mod_edges)}, ALTERNATIVE_TO={len(alt_edges)})"
            )
        else:
            print(
                f"✓ all {len(before_titles)} original scenarios preserved server-side; "
                f"alternative linked via ALTERNATIVE_TO + MODIFIES"
            )
        page.wait_for_timeout(400)
        page.screenshot(path=str(SHOTS / "06-whatif.png"))

        # Bonus: check the computation feed shows real event sequence numbers
        feed_items = page.locator(".rail-feed li").count()
        if feed_items < 5:
            failures.append(f"computation feed too thin: {feed_items} items")
        else:
            print(f"✓ computation feed carries {feed_items} real backend events")

        browser.close()

    print()
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" ✗", f)
        return 1
    print("ALL E2E CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
