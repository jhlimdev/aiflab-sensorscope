"""Run against a live default demo server; saves real desktop/mobile screenshots."""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("browser-artifacts"))
    parser.add_argument("--browser-channel", default=None, help="Use installed chrome or msedge")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=args.browser_channel)
        page = browser.new_page(viewport={"width": 1440, "height": 1200}, device_scale_factor=1)
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(args.url, wait_until="networkidle")
        expect(page.locator("#connection")).to_contain_text("서버 연결됨")
        expect(page.locator(".machine-card")).to_have_count(3)
        page.locator('[data-machine="motor-02"]').click()
        page.locator('[data-metric="current"]').click()
        expect(page.locator("#trend-heading")).to_contain_text("모터 02")
        expect(page.locator("#current-unit")).to_have_text("A")
        page.locator("#inject").click()
        expect(page.locator("#feedback")).to_contain_text("이상 주입을 요청했습니다")
        expect(page.locator('[data-machine="motor-02"] .pill')).to_have_text(
            "이상 감지", timeout=10000
        )
        expect(page.locator("#event-rows")).to_contain_text("전류", timeout=10000)
        page.locator("#event-filter").select_option("selected")
        expect(page.locator("#event-scope")).to_contain_text("선택 설비")
        page.wait_for_function("Chart.getChart('sensor-chart').data.datasets[0].data.length > 2")
        page.screenshot(path=str(args.output / "dashboard.png"), full_page=True)
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        mobile.on("pageerror", lambda exc: errors.append(str(exc)))
        mobile.goto(args.url, wait_until="networkidle")
        expect(mobile.locator("#connection")).to_contain_text("서버 연결됨")
        mobile.screenshot(path=str(args.output / "dashboard-mobile.png"), full_page=True)
        assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
            "Mobile overflow"
        )
        page.route("**/api/overview", lambda route: route.abort())
        expect(page.locator("#error")).to_be_visible(timeout=8000)
        expect(page.locator("#connection")).to_contain_text("연결 확인 필요")
        expect(page.locator("#inject")).to_be_disabled()
        page.unroute("**/api/overview")
        expect(page.locator("#connection")).to_contain_text("서버 연결됨", timeout=8000)
        browser.close()
    assert not errors, errors
    print(
        "PASS: chart, machine/metric selection, injection, event filter, mobile layout, disconnect/reconnect; no page errors"
    )


if __name__ == "__main__":
    main()
