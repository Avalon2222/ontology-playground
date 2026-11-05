"""
scripts/tangkap_layar.py - Mengambil screenshot setiap tab untuk README (butuh Playwright + Chromium).

    streamlit run app.py --server.port 8601 --server.headless true &
    python scripts/tangkap_layar.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8601"
KELUARAN = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
TAB = [
    ("Ontology", "01_ontology.png"),
    ("Objects", "02_objects.png"),
    ("Graph", "03_graph.png"),
    ("SQL", "05_sql.png"),
    ("Data & Sources", "06_data.png"),
    ("How it works", "07_cara_kerja.png"),
]


def main() -> None:
    KELUARAN.mkdir(parents=True, exist_ok=True)
    exe = sys.argv[1] if len(sys.argv) > 1 else None
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.goto(URL, wait_until="networkidle", timeout=120_000)
        page.wait_for_selector("[role='tab']", timeout=180_000)
        page.wait_for_timeout(5000)
        for nama, berkas in TAB:
            page.get_by_role("tab", name=nama, exact=False).click()
            page.wait_for_timeout(4000)
            page.screenshot(path=str(KELUARAN / berkas))
            print("ok", berkas)
        # Ask: klik dua contoh pertanyaan supaya ada percakapan di layar
        page.get_by_role("tab", name="Ask").click()
        page.wait_for_timeout(2000)
        page.get_by_role("button", name="Kapal berbendera asing mana yang mengangkut nikel?").click()
        page.wait_for_timeout(4000)
        page.get_by_role("button", name="Pelabuhan mana yang paling banyak pelayaran?").click()
        page.wait_for_timeout(4000)
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(KELUARAN / "04_ask.png"))
        print("ok 04_ask.png")
        # Learning mode di tab Objects
        page.get_by_text("Learning mode").first.click()
        page.wait_for_timeout(1500)
        page.get_by_role("tab", name="Objects").click()
        page.wait_for_timeout(3000)
        page.mouse.wheel(0, 1400)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(KELUARAN / "08_learning_mode.png"))
        print("ok 08_learning_mode.png")
        browser.close()


if __name__ == "__main__":
    main()
