#!/usr/bin/env python3
"""
End-to-end Playwright tests for the PriceMap dev dashboard.
Starts the server, runs a real browser, tests every page and interaction.

Usage:
    cd scripts && python test_dashboard.py
"""

import subprocess
import sys
import time

from playwright.sync_api import sync_playwright, expect

PORT = 8599  # Use a different port to avoid conflicts
BASE = f"http://localhost:{PORT}"
server_proc = None


def start_server():
    global server_proc
    server_proc = subprocess.Popen(
        [sys.executable, "-c",
         f"import uvicorn; uvicorn.run('dashboard.app:app', host='127.0.0.1', port={PORT})"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # Wait for server to be ready
    import httpx
    for _ in range(30):
        try:
            r = httpx.get(f"{BASE}/", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("Server didn't start")


def stop_server():
    if server_proc:
        server_proc.terminate()
        server_proc.wait(timeout=5)


def run_tests():
    passed = 0
    failed = 0
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        page.set_default_timeout(10000)

        def test(name, fn):
            nonlocal passed, failed
            try:
                fn()
                passed += 1
                print(f"  PASS  {name}")
            except Exception as e:
                failed += 1
                msg = str(e).split("\n")[0][:120]
                errors.append((name, msg))
                print(f"  FAIL  {name}: {msg}")

        # ── HOME PAGE ──

        def test_home():
            page.goto(BASE, wait_until="networkidle")
            assert "PriceMap" in page.content()
            assert "mt_remax" in page.content()
            assert "mt_maltapark" in page.content()
            assert "bg_imot" in page.content()

        test("Home page loads", test_home)

        def test_home_nav_links():
            page.goto(BASE, wait_until="networkidle")
            assert 'href="/search"' in page.content()
            assert 'href="/stats"' in page.content()

        test("Home nav links", test_home_nav_links)

        def test_home_collection_click():
            page.goto(BASE, wait_until="networkidle")
            page.click('a[href="/browse/mt_remax"]')
            page.wait_for_url("**/browse/mt_remax**")

        test("Home → collection click", test_home_collection_click)

        # ── BROWSE PAGE ──

        def test_browse_loads():
            page.goto(f"{BASE}/browse/mt_remax")
            expect(page.locator("h1")).to_contain_text("mt_remax")
            # Should show property cards with images
            cards = page.locator("div.grid a.block")
            assert cards.count() > 0, "No property cards found"

        test("Browse page loads", test_browse_loads)

        def test_browse_property_cards():
            page.goto(f"{BASE}/browse/mt_remax")
            # Each card should have price
            prices = page.locator("div.text-lg.font-bold.text-blue-600")
            assert prices.count() > 0
            first_price = prices.first.text_content()
            assert "€" in first_price, f"Price should contain €, got: {first_price}"

        test("Browse shows prices", test_browse_property_cards)

        def test_browse_images():
            page.goto(f"{BASE}/browse/mt_remax")
            images = page.locator("div.grid img")
            assert images.count() > 0, "No images on browse page"

        test("Browse shows images", test_browse_images)

        def test_browse_pagination():
            page.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            assert "Next" in page.content()
            page.goto(f"{BASE}/browse/mt_remax?page=2", wait_until="networkidle")
            assert "Page 2" in page.content()

        test("Browse pagination", test_browse_pagination)

        def test_browse_filter_type():
            page.goto(f"{BASE}/browse/mt_remax?prop_type=penthouse", wait_until="networkidle")
            assert "penthouse" in page.content()
            # Verify filter actually reduces count
            page.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            all_text = page.locator("h1").text_content()
            page.goto(f"{BASE}/browse/mt_remax?prop_type=penthouse", wait_until="networkidle")
            filtered_text = page.locator("h1").text_content()
            # Filtered count should be less
            import re
            all_n = int(re.search(r"\((\d+)", all_text).group(1))
            filt_n = int(re.search(r"\((\d+)", filtered_text).group(1))
            assert filt_n < all_n, f"Filter didn't reduce: {filt_n} vs {all_n}"

        test("Browse filter by type", test_browse_filter_type)

        def test_browse_filter_price():
            page.goto(f"{BASE}/browse/mt_remax?min_price=200000&max_price=400000", wait_until="networkidle")
            prices = page.locator("div.text-lg.font-bold.text-blue-600")
            assert prices.count() > 0
            assert "€" in prices.first.text_content()

        test("Browse filter by price", test_browse_filter_price)

        def test_browse_search():
            page.goto(f"{BASE}/browse/mt_remax?q=Sliema", wait_until="networkidle")
            assert "mt_remax" in page.content()

        test("Browse search", test_browse_search)

        def test_browse_sort():
            page.goto(f"{BASE}/browse/mt_remax?sort=price_desc", wait_until="networkidle")
            prices = page.locator("div.text-lg.font-bold.text-blue-600")
            if prices.count() >= 2:
                p1 = prices.nth(0).text_content().replace("€","").replace(",","").replace("—","0").strip()
                p2 = prices.nth(1).text_content().replace("€","").replace(",","").replace("—","0").strip()
                assert float(p1) >= float(p2), f"Not sorted desc: {p1} < {p2}"

        test("Browse sort price desc", test_browse_sort)

        def test_browse_form_submit():
            page.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            page.select_option("select[name=prop_type]", "penthouse")
            with page.expect_navigation():
                page.click("button[type=submit]")
            assert "prop_type=penthouse" in page.url
            assert "penthouse" in page.content()

        test("Browse form submit", test_browse_form_submit)

        def test_search_form_submit():
            page.goto(f"{BASE}/search", wait_until="networkidle")
            page.fill("input[name=q]", "Valletta")
            with page.expect_navigation():
                page.click("button[type=submit]")
            assert "q=Valletta" in page.url

        test("Search form submit", test_search_form_submit)

        def test_browse_clear_filters():
            page.goto(f"{BASE}/browse/mt_remax?q=test&prop_type=house&min_price=100000&max_price=500000")
            clear = page.locator("a", has_text="Clear")
            expect(clear).to_be_visible()
            clear.click()
            page.wait_for_url(f"{BASE}/browse/mt_remax")

        test("Browse clear filters", test_browse_clear_filters)

        def test_browse_maltapark():
            page.goto(f"{BASE}/browse/mt_maltapark")
            expect(page.locator("h1")).to_contain_text("mt_maltapark")
            cards = page.locator("div.grid a.block")
            assert cards.count() > 0

        test("Browse MaltaPark", test_browse_maltapark)

        def test_browse_imot():
            page.goto(f"{BASE}/browse/bg_imot")
            expect(page.locator("h1")).to_contain_text("bg_imot")
            cards = page.locator("div.grid a.block")
            assert cards.count() > 0

        test("Browse Imot.bg", test_browse_imot)

        # ── PROPERTY DETAIL ──

        def test_property_detail():
            page.goto(f"{BASE}/browse/mt_remax")
            # Click first property card
            page.locator("div.grid a.block").first.click()
            page.wait_for_url("**/property/**")
            # Should show price
            price = page.locator("div.text-3xl.font-bold.text-blue-600")
            expect(price).to_be_visible()

        test("Property detail via click", test_property_detail)

        def test_property_detail_sections():
            page.goto(f"{BASE}/property/mt_remax/240271042-233", wait_until="networkidle")
            content = page.content()
            assert "All Parsed Data" in content
            assert "Metadata" in content
            assert "History" in content

        test("Property detail sections", test_property_detail_sections)

        def test_property_detail_images():
            page.goto(f"{BASE}/property/mt_remax/240271042-233")
            images = page.locator("img[src*='/image/']")
            assert images.count() > 0, "No images on detail page"

        test("Property detail images", test_property_detail_images)

        def test_property_detail_history():
            page.goto(f"{BASE}/property/mt_remax/240271042-233")
            # Should show at least "created" event
            expect(page.locator("span.badge", has_text="created").first).to_be_visible()

        test("Property detail history", test_property_detail_history)

        def test_property_detail_back_link():
            page.goto(f"{BASE}/property/mt_remax/240271042-233")
            back = page.locator("a", has_text="Back to mt_remax")
            expect(back).to_be_visible()
            back.click()
            page.wait_for_url("**/browse/mt_remax**")

        test("Property detail back link", test_property_detail_back_link)

        def test_property_detail_original_link():
            page.goto(f"{BASE}/property/mt_remax/240271042-233")
            link = page.locator("a", has_text="View original listing")
            expect(link).to_be_visible()
            href = link.get_attribute("href")
            assert "remax-malta.com" in href

        test("Property detail original link", test_property_detail_original_link)

        def test_property_404():
            page.goto(f"{BASE}/property/mt_remax/nonexistent")
            expect(page.locator("text=Not found")).to_be_visible()

        test("Property 404", test_property_404)

        # ── SEARCH ──

        def test_search_page():
            page.goto(f"{BASE}/search")
            expect(page.locator("text=Search Properties")).to_be_visible()
            expect(page.locator("input[name=q]")).to_be_visible()

        test("Search page loads", test_search_page)

        def test_search_query():
            page.goto(f"{BASE}/search?q=Sliema", wait_until="networkidle")
            assert "result" in page.content().lower()
            results = page.locator("a.block")
            assert results.count() > 0

        test("Search with results", test_search_query)

        def test_search_no_results():
            page.goto(f"{BASE}/search?q=zzznonexistent12345", wait_until="networkidle")
            assert "No results" in page.content()

        test("Search no results", test_search_no_results)

        def test_search_country_filter():
            page.goto(f"{BASE}/search?q=apartment&country=BG", wait_until="networkidle")
            content = page.content()
            assert "result" in content.lower()

        test("Search country filter", test_search_country_filter)

        def test_search_click_result():
            page.goto(f"{BASE}/search?q=Sliema")
            page.locator("a.block").first.click()
            page.wait_for_url("**/property/**")
            price = page.locator("div.text-3xl.font-bold.text-blue-600")
            expect(price).to_be_visible()

        test("Search → click result", test_search_click_result)

        # ── STATS ──

        def test_stats_page():
            page.goto(f"{BASE}/stats")
            expect(page.locator("text=Market Statistics")).to_be_visible()
            expect(page.locator("text=By Country")).to_be_visible()
            expect(page.locator("text=By Property Type")).to_be_visible()
            expect(page.locator("text=Top Localities")).to_be_visible()

        test("Stats page loads", test_stats_page)

        def test_stats_country_data():
            page.goto(f"{BASE}/stats")
            expect(page.locator("td", has_text="MT")).to_be_visible()
            expect(page.locator("td", has_text="BG")).to_be_visible()

        test("Stats shows countries", test_stats_country_data)

        def test_stats_type_data():
            page.goto(f"{BASE}/stats")
            expect(page.locator("td", has_text="apartment")).to_be_visible()
            expect(page.locator("td", has_text="penthouse")).to_be_visible()

        test("Stats shows property types", test_stats_type_data)

        def test_stats_history_events():
            page.goto(f"{BASE}/stats")
            expect(page.locator("text=Change History Events")).to_be_visible()

        test("Stats shows history events", test_stats_history_events)

        # ── NAVIGATION ──

        def test_nav_search():
            page.goto(BASE)
            page.locator("nav a", has_text="Search").click()
            page.wait_for_url("**/search**")

        test("Nav → Search", test_nav_search)

        def test_nav_stats():
            page.goto(BASE)
            page.locator("nav a", has_text="Stats").click()
            page.wait_for_url("**/stats**")

        test("Nav → Stats", test_nav_stats)

        def test_nav_home():
            page.goto(f"{BASE}/stats")
            page.locator("a", has_text="PriceMap").first.click()
            page.wait_for_url(BASE + "/")

        test("Nav → Home", test_nav_home)

        browser.close()

    return passed, failed, errors


def main():
    print("Starting dashboard server...")
    start_server()
    print(f"Server ready at {BASE}\n")

    try:
        print("Running Playwright tests:\n")
        passed, failed, errors = run_tests()

        print(f"\n{'='*60}")
        print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
        if errors:
            print(f"\nFailed tests:")
            for name, msg in errors:
                print(f"  {name}: {msg}")
        print(f"{'='*60}")

        sys.exit(0 if failed == 0 else 1)
    finally:
        stop_server()


if __name__ == "__main__":
    main()
