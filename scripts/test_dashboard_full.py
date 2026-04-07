#!/usr/bin/env python3
"""
Full Playwright test suite for the PriceMap dev dashboard.
Tests every page, every interactive element, edge cases, and visual correctness.
"""

import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

PORT = 8599
BASE = f"http://localhost:{PORT}"
server_proc = None


def start_server():
    global server_proc
    server_proc = subprocess.Popen(
        [sys.executable, "-c",
         f"import uvicorn; uvicorn.run('dashboard.app:app', host='127.0.0.1', port={PORT})"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    import httpx
    for _ in range(30):
        try:
            if httpx.get(f"{BASE}/", timeout=2).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("Server didn't start")


def stop_server():
    if server_proc:
        server_proc.terminate()
        server_proc.wait(timeout=5)


passed = 0
failed = 0
errors = []


def test(name, fn, page):
    global passed, failed
    try:
        fn(page)
        passed += 1
        print(f"  PASS  {name}")
    except Exception as e:
        failed += 1
        msg = str(e).split("\n")[0][:140]
        errors.append((name, msg))
        print(f"  FAIL  {name}: {msg}")


def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(15000)

        # ══════════════════════════════════════════════
        print("\n── HOME PAGE ──")
        # ══════════════════════════════════════════════

        def test_home_loads(pg):
            pg.goto(BASE, wait_until="networkidle")
            assert "PriceMap" in pg.content()
            assert "Dashboard" in pg.content()
        test("Home page loads", test_home_loads, page)

        def test_home_stats_cards(pg):
            pg.goto(BASE, wait_until="networkidle")
            cards = pg.locator("div.text-3xl.font-bold").all()
            assert len(cards) >= 2, f"Expected 2+ stat cards, got {len(cards)}"
            # First card should be total count (> 1000)
            total = cards[0].text_content().replace(",", "")
            assert int(total) > 1000, f"Total props should be >1000, got {total}"
        test("Home stat cards show real counts", test_home_stats_cards, page)

        def test_home_collections(pg):
            pg.goto(BASE, wait_until="networkidle")
            for name in ["mt_remax", "mt_maltapark", "bg_imot"]:
                assert name in pg.content(), f"Missing collection {name}"
        test("Home shows all 3 collections", test_home_collections, page)

        def test_home_scrape_runs_table(pg):
            pg.goto(BASE, wait_until="networkidle")
            rows = pg.locator("table tbody tr").all()
            assert len(rows) > 0, "Scrape runs table is empty"
        test("Home shows scrape runs", test_home_scrape_runs_table, page)

        def test_home_click_collection(pg):
            pg.goto(BASE, wait_until="networkidle")
            pg.click('a[href="/browse/mt_remax"]')
            pg.wait_for_url("**/browse/mt_remax**")
        test("Home → click collection link", test_home_click_collection, page)

        # ══════════════════════════════════════════════
        print("\n── BROWSE PAGE ──")
        # ══════════════════════════════════════════════

        def test_browse_loads(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            heading = pg.locator("h1").text_content()
            assert "mt_remax" in heading
            # Should show total count in parentheses
            import re
            m = re.search(r"\((\d+)", heading)
            assert m, f"No count in heading: {heading}"
            count = int(m.group(1))
            assert count > 1000, f"Expected >1000 in heading, got {count}"
        test("Browse loads with count", test_browse_loads, page)

        def test_browse_has_cards(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            cards = pg.locator("div.grid > a").all()
            assert len(cards) > 0, "No property cards"
            assert len(cards) <= 24, f"Expected max 24 cards per page, got {len(cards)}"
        test("Browse shows property cards (max 24)", test_browse_has_cards, page)

        def test_browse_card_has_price(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            prices = pg.locator("div.text-lg.font-bold.text-blue-600").all()
            assert len(prices) > 0, "No prices shown"
            first = prices[0].text_content()
            assert "€" in first or "—" in first, f"Price format wrong: {first}"
        test("Browse cards show prices", test_browse_card_has_price, page)

        def test_browse_card_has_image(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            imgs = pg.locator("div.grid img").all()
            # At least some cards should have images
            assert len(imgs) > 0, "No images on browse page"
        test("Browse cards show images", test_browse_card_has_image, page)

        def test_browse_card_click(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            pg.locator("div.grid > a").first.click()
            pg.wait_for_url("**/property/**")
        test("Browse card → property detail", test_browse_card_click, page)

        # Pagination
        def test_browse_pagination(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            content = pg.content()
            assert "Page 1 of" in content, "Missing pagination"
            assert "Next" in content, "Missing Next link"
        test("Browse shows pagination", test_browse_pagination, page)

        def test_browse_page2(pg):
            pg.goto(f"{BASE}/browse/mt_remax?page=2&min_price=&max_price=", wait_until="networkidle")
            assert "Page 2 of" in pg.content()
            cards = pg.locator("div.grid > a").all()
            assert len(cards) > 0, "Page 2 has no cards"
        test("Browse pagination page 2", test_browse_page2, page)

        def test_browse_prev(pg):
            pg.goto(f"{BASE}/browse/mt_remax?page=2&min_price=&max_price=", wait_until="networkidle")
            prev_link = pg.locator("a:has-text('Prev')")
            assert prev_link.is_visible(), "No Prev link on page 2"
            href = prev_link.get_attribute("href")
            assert "page=1" in href, f"Prev link doesn't go to page 1: {href}"
        test("Browse pagination Prev link exists", test_browse_prev, page)

        # Filters via form submit
        def test_browse_filter_type_form(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            pg.select_option("select[name=prop_type]", "penthouse")
            with pg.expect_navigation():
                pg.click("button[type=submit]")
            assert "prop_type=penthouse" in pg.url
            content = pg.content()
            # Heading count should be less than total
            import re
            m = re.search(r"\((\d+) properties\)", content)
            if m:
                assert int(m.group(1)) < 32000
        test("Browse filter type via form submit", test_browse_filter_type_form, page)

        def test_browse_filter_search_form(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            pg.fill("input[name=q]", "Valletta")
            with pg.expect_navigation():
                pg.click("button[type=submit]")
            assert "q=Valletta" in pg.url
        test("Browse search via form submit", test_browse_filter_search_form, page)

        def test_browse_filter_price_form(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            pg.fill("input[name=min_price]", "200000")
            pg.fill("input[name=max_price]", "400000")
            with pg.expect_navigation():
                pg.click("button[type=submit]")
            assert "min_price=200000" in pg.url
        test("Browse price range via form submit", test_browse_filter_price_form, page)

        def test_browse_sort_form(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            pg.select_option("select[name=sort]", "price_desc")
            with pg.expect_navigation():
                pg.click("button[type=submit]")
            assert "sort=price_desc" in pg.url
        test("Browse sort via form submit", test_browse_sort_form, page)

        # Filter via direct URL (as browser sends them)
        for ptype in ["apartment", "penthouse", "house", "maisonette", "studio", "commercial", "parking", "land"]:
            def test_filter(pg, pt=ptype):
                pg.goto(f"{BASE}/browse/mt_remax?prop_type={pt}&min_price=&max_price=", wait_until="networkidle")
                assert pg.locator("h1").text_content()  # no crash
            test(f"Browse filter type={ptype}", test_filter, page)

        def test_browse_clear_filters(pg):
            pg.goto(f"{BASE}/browse/mt_remax?q=test&prop_type=house&min_price=100000&max_price=500000", wait_until="networkidle")
            clear = pg.locator("a:has-text('Clear')")
            assert clear.is_visible(), "Clear link not shown when filters active"
            clear.click()
            pg.wait_for_url(f"{BASE}/browse/mt_remax")
        test("Browse clear filters link", test_browse_clear_filters, page)

        def test_browse_empty_result(pg):
            pg.goto(f"{BASE}/browse/mt_remax?q=zzzzzznotexist99999&min_price=&max_price=", wait_until="networkidle")
            assert "No properties match" in pg.content()
        test("Browse shows 'no results' message", test_browse_empty_result, page)

        # Sort correctness
        def test_browse_sort_price_desc(pg):
            pg.goto(f"{BASE}/browse/mt_remax?sort=price_desc&min_price=&max_price=", wait_until="networkidle")
            prices = pg.locator("div.text-lg.font-bold.text-blue-600").all()
            if len(prices) >= 2:
                def parse_price(el):
                    t = el.text_content().replace("€", "").replace(",", "").replace("—", "0").strip()
                    try:
                        return float(t)
                    except ValueError:
                        return 0
                p1 = parse_price(prices[0])
                p2 = parse_price(prices[1])
                assert p1 >= p2, f"Not sorted desc: {p1} < {p2}"
        test("Browse sort price_desc is correct", test_browse_sort_price_desc, page)

        def test_browse_sort_price_asc(pg):
            pg.goto(f"{BASE}/browse/mt_remax?sort=price_asc&min_price=&max_price=", wait_until="networkidle")
            prices = pg.locator("div.text-lg.font-bold.text-blue-600").all()
            if len(prices) >= 2:
                def parse_price(el):
                    t = el.text_content().replace("€", "").replace(",", "").replace("—", "0").strip()
                    try:
                        return float(t)
                    except ValueError:
                        return float("inf")
                p1 = parse_price(prices[0])
                p2 = parse_price(prices[1])
                assert p1 <= p2, f"Not sorted asc: {p1} > {p2}"
        test("Browse sort price_asc is correct", test_browse_sort_price_asc, page)

        # All collections
        for coll in ["mt_maltapark", "bg_imot"]:
            def test_coll(pg, c=coll):
                pg.goto(f"{BASE}/browse/{c}", wait_until="networkidle")
                assert c in pg.locator("h1").text_content()
                cards = pg.locator("div.grid > a").all()
                assert len(cards) > 0, f"No cards for {c}"
            test(f"Browse collection {coll}", test_coll, page)

        # ══════════════════════════════════════════════
        print("\n── PROPERTY DETAIL ──")
        # ══════════════════════════════════════════════

        def test_detail_loads(pg):
            # Find a known property
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            link = pg.locator("div.grid > a").first.get_attribute("href")
            pg.goto(f"{BASE}{link}", wait_until="networkidle")
            # Should have price
            price = pg.locator("div.text-3xl.font-bold.text-blue-600")
            assert price.is_visible(), "No price on detail page"
        test("Property detail loads", test_detail_loads, page)

        def test_detail_sections(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            link = pg.locator("div.grid > a").first.get_attribute("href")
            pg.goto(f"{BASE}{link}", wait_until="networkidle")
            content = pg.content()
            for section in ["All Parsed Data", "Metadata", "History"]:
                assert section in content, f"Missing section: {section}"
        test("Property detail has all sections", test_detail_sections, page)

        def test_detail_images(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            link = pg.locator("div.grid > a").first.get_attribute("href")
            pg.goto(f"{BASE}{link}", wait_until="networkidle")
            imgs = pg.locator("img[src*='/image/']").all()
            assert len(imgs) > 0, "No images on detail page"
            # Verify first image actually loads (not 404)
            src = imgs[0].get_attribute("src")
            resp = pg.request.get(f"{BASE}{src}" if src.startswith("/") else src)
            assert resp.status == 200, f"Image returned {resp.status}: {src}"
        test("Property detail images load", test_detail_images, page)

        def test_detail_history(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            link = pg.locator("div.grid > a").first.get_attribute("href")
            pg.goto(f"{BASE}{link}", wait_until="networkidle")
            # Should have at least a "created" event
            events = pg.locator("span.badge:has-text('created')").all()
            assert len(events) > 0, "No 'created' history event"
        test("Property detail shows history", test_detail_history, page)

        def test_detail_parsed_data(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            link = pg.locator("div.grid > a").first.get_attribute("href")
            pg.goto(f"{BASE}{link}", wait_until="networkidle")
            # "All Parsed Data" section should have key-value rows
            rows = pg.locator("text=source").all()
            assert len(rows) > 0, "No 'source' field in parsed data"
        test("Property detail shows parsed data", test_detail_parsed_data, page)

        def test_detail_back_link(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            link = pg.locator("div.grid > a").first.get_attribute("href")
            pg.goto(f"{BASE}{link}", wait_until="networkidle")
            pg.click("a:has-text('Back to')")
            pg.wait_for_url("**/browse/mt_remax**")
        test("Property detail back link works", test_detail_back_link, page)

        def test_detail_original_link(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            link = pg.locator("div.grid > a").first.get_attribute("href")
            pg.goto(f"{BASE}{link}", wait_until="networkidle")
            orig = pg.locator("a:has-text('View original listing')")
            if orig.count() > 0:
                href = orig.get_attribute("href")
                assert "remax-malta.com" in href or "maltapark" in href or "imot.bg" in href
        test("Property detail external link", test_detail_original_link, page)

        def test_detail_gps_link(pg):
            pg.goto(f"{BASE}/browse/mt_remax?sort=newest&min_price=&max_price=", wait_until="networkidle")
            link = pg.locator("div.grid > a").first.get_attribute("href")
            pg.goto(f"{BASE}{link}", wait_until="networkidle")
            osm = pg.locator("a:has-text('OpenStreetMap')")
            if osm.count() > 0:
                href = osm.get_attribute("href")
                assert "openstreetmap.org" in href
        test("Property detail GPS link", test_detail_gps_link, page)

        def test_detail_404(pg):
            pg.goto(f"{BASE}/property/mt_remax/nonexistent_xyz", wait_until="networkidle")
            assert "Not found" in pg.content()
        test("Property detail 404", test_detail_404, page)

        # Test a property from each collection
        for coll in ["mt_maltapark", "bg_imot"]:
            def test_detail_coll(pg, c=coll):
                pg.goto(f"{BASE}/browse/{c}", wait_until="networkidle")
                link = pg.locator("div.grid > a").first.get_attribute("href")
                pg.goto(f"{BASE}{link}", wait_until="networkidle")
                assert pg.locator("div.text-3xl.font-bold.text-blue-600").is_visible()
            test(f"Property detail from {coll}", test_detail_coll, page)

        # ══════════════════════════════════════════════
        print("\n── SEARCH ──")
        # ══════════════════════════════════════════════

        def test_search_empty(pg):
            pg.goto(f"{BASE}/search", wait_until="networkidle")
            assert "Search Properties" in pg.content()
            assert pg.locator("input[name=q]").is_visible()
            assert pg.locator("button[type=submit]").is_visible()
        test("Search page loads", test_search_empty, page)

        def test_search_form_submit(pg):
            pg.goto(f"{BASE}/search", wait_until="networkidle")
            pg.fill("input[name=q]", "Sliema")
            with pg.expect_navigation():
                pg.click("button[type=submit]")
            assert "q=Sliema" in pg.url
            assert "result" in pg.content().lower()
        test("Search form submit", test_search_form_submit, page)

        def test_search_results(pg):
            pg.goto(f"{BASE}/search?q=Sliema", wait_until="networkidle")
            results = pg.locator("a.block").all()
            assert len(results) > 0, "No search results for Sliema"
            # Each result should have price
            prices = pg.locator("div.text-lg.font-bold.text-blue-600").all()
            assert len(prices) > 0
        test("Search shows results with prices", test_search_results, page)

        def test_search_click_result(pg):
            pg.goto(f"{BASE}/search?q=Sliema", wait_until="networkidle")
            pg.locator("a.block").first.click()
            pg.wait_for_url("**/property/**")
        test("Search result → property detail", test_search_click_result, page)

        def test_search_no_results(pg):
            pg.goto(f"{BASE}/search?q=zzzznonexist12345", wait_until="networkidle")
            assert "No results" in pg.content()
        test("Search shows no results message", test_search_no_results, page)

        def test_search_country_filter(pg):
            pg.goto(f"{BASE}/search", wait_until="networkidle")
            pg.fill("input[name=q]", "apartment")
            pg.select_option("select[name=country]", "BG")
            with pg.expect_navigation():
                pg.click("button[type=submit]")
            assert "country=BG" in pg.url
        test("Search with country filter", test_search_country_filter, page)

        def test_search_cyrillic(pg):
            pg.goto(f"{BASE}/search?q=София", wait_until="networkidle")
            # Should not crash; may or may not have results
            assert pg.locator("h1").is_visible()
        test("Search with Cyrillic text", test_search_cyrillic, page)

        def test_search_xss(pg):
            pg.goto(f'{BASE}/search?q=<script>alert(1)</script>', wait_until="networkidle")
            assert "<script>alert(1)</script>" not in pg.content()
        test("Search XSS protection", test_search_xss, page)

        def test_search_result_images(pg):
            pg.goto(f"{BASE}/search?q=Sliema", wait_until="networkidle")
            imgs = pg.locator("a.block img").all()
            assert len(imgs) > 0, "No thumbnails in search results"
        test("Search results show thumbnails", test_search_result_images, page)

        # ══════════════════════════════════════════════
        print("\n── STATS ──")
        # ══════════════════════════════════════════════

        def test_stats_loads(pg):
            pg.goto(f"{BASE}/stats", wait_until="networkidle")
            assert "Market Statistics" in pg.content()
        test("Stats page loads", test_stats_loads, page)

        def test_stats_countries(pg):
            pg.goto(f"{BASE}/stats", wait_until="networkidle")
            content = pg.content()
            assert "MT" in content, "Missing MT in stats"
            assert "BG" in content, "Missing BG in stats"
        test("Stats shows both countries", test_stats_countries, page)

        def test_stats_types(pg):
            pg.goto(f"{BASE}/stats", wait_until="networkidle")
            content = pg.content()
            for t in ["apartment", "penthouse", "house"]:
                assert t in content, f"Missing type {t} in stats"
        test("Stats shows property types", test_stats_types, page)

        def test_stats_localities(pg):
            pg.goto(f"{BASE}/stats", wait_until="networkidle")
            assert "Top Localities" in pg.content()
            rows = pg.locator("table").last.locator("tbody tr").all()
            assert len(rows) > 5, f"Expected >5 localities, got {len(rows)}"
        test("Stats shows locality table", test_stats_localities, page)

        def test_stats_bars(pg):
            pg.goto(f"{BASE}/stats", wait_until="networkidle")
            bars = pg.locator("div.bg-blue-500.rounded-full").all()
            assert len(bars) > 0, "No distribution bars in stats"
        test("Stats shows distribution bars", test_stats_bars, page)

        def test_stats_history_section(pg):
            pg.goto(f"{BASE}/stats", wait_until="networkidle")
            assert "Change History Events" in pg.content()
        test("Stats shows history events section", test_stats_history_section, page)

        # ══════════════════════════════════════════════
        print("\n── NAVIGATION ──")
        # ══════════════════════════════════════════════

        def test_nav_links(pg):
            pg.goto(BASE, wait_until="networkidle")
            nav = pg.locator("nav")
            for text in ["Search", "Stats", "mt_remax", "mt_maltapark", "bg_imot"]:
                assert nav.locator(f"a:has-text('{text}')").count() > 0, f"Missing nav link: {text}"
        test("Nav has all links", test_nav_links, page)

        def test_nav_search(pg):
            pg.goto(BASE, wait_until="networkidle")
            pg.locator("nav a:has-text('Search')").click()
            pg.wait_for_url("**/search**")
        test("Nav → Search", test_nav_search, page)

        def test_nav_stats(pg):
            pg.goto(BASE, wait_until="networkidle")
            pg.locator("nav a:has-text('Stats')").click()
            pg.wait_for_url("**/stats**")
        test("Nav → Stats", test_nav_stats, page)

        def test_nav_logo_home(pg):
            pg.goto(f"{BASE}/stats", wait_until="networkidle")
            pg.locator("nav a:has-text('PriceMap')").click()
            pg.wait_for_url(BASE + "/")
        test("Nav logo → Home", test_nav_logo_home, page)

        # ══════════════════════════════════════════════
        print("\n── EDGE CASES ──")
        # ══════════════════════════════════════════════

        def test_edge_huge_page(pg):
            pg.goto(f"{BASE}/browse/mt_remax?page=99999&min_price=&max_price=", wait_until="networkidle")
            # Should not crash; should show last page or empty
            assert pg.locator("h1").is_visible()
        test("Browse huge page number", test_edge_huge_page, page)

        def test_edge_negative_price(pg):
            pg.goto(f"{BASE}/browse/mt_remax?min_price=-100&max_price=&sort=newest", wait_until="networkidle")
            assert pg.locator("h1").is_visible()
        test("Browse negative price filter", test_edge_negative_price, page)

        def test_edge_invalid_collection(pg):
            pg.goto(f"{BASE}/browse/nonexistent_xyz", wait_until="networkidle")
            # Should not crash (empty collection)
            assert pg.locator("h1").is_visible()
        test("Browse nonexistent collection", test_edge_invalid_collection, page)

        def test_edge_special_chars_search(pg):
            pg.goto(f"{BASE}/search?q=%22hello%22+%26+%27world%27", wait_until="networkidle")
            assert pg.locator("h1").is_visible()
        test("Search with special chars (&, quotes)", test_edge_special_chars_search, page)

        def test_edge_empty_form_submit(pg):
            pg.goto(f"{BASE}/browse/mt_remax", wait_until="networkidle")
            # Submit form with everything empty
            with pg.expect_navigation():
                pg.click("button[type=submit]")
            assert pg.locator("h1").is_visible()
        test("Browse submit empty form", test_edge_empty_form_submit, page)

        def test_edge_image_404(pg):
            resp = pg.request.get(f"{BASE}/image/nonexistent_file.jpg")
            assert resp.status == 404
        test("Image 404 for missing file", test_edge_image_404, page)

        def test_edge_very_long_search(pg):
            long_q = "a" * 500
            pg.goto(f"{BASE}/search?q={long_q}", wait_until="networkidle")
            assert pg.locator("h1").is_visible()
        test("Search with very long query", test_edge_very_long_search, page)

        browser.close()


def main():
    print("Starting dashboard server...")
    start_server()
    print(f"Server ready at {BASE}\n")

    try:
        run_tests()
        print(f"\n{'='*60}")
        print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
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
