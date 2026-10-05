"""Remote Linux integration: real CloakBrowser renders JavaScript and saves HTML."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from capture_page import ensure_cloakbrowser, save_html
import json
import shutil


class BrowserIntegrationTests(unittest.TestCase):
    def test_real_browser_saves_javascript_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text(
                '<html><head><meta charset="utf-8"><link rel="stylesheet" href="css/main.css"></head>'
                '<body><p id="result">加载中</p><div id="tile"></div>'
                '<img id="picture" src="picture.svg"><img id="responsive" src="missing.svg" srcset="picture.svg 1x">'
                '<svg width="20" height="20"><use href="sprite.svg#icon"></use></svg>'
                '<a id="video" href="/video/123">视频</a><canvas id="canvas" width="10" height="10"></canvas>'
                '<script>setTimeout(() => {document.querySelector("#result").textContent = '
                '"罗生门：浏览器渲染成功"; document.querySelector("#canvas").getContext("2d").fillRect(0,0,10,10);}, 100);'
                '</script></body></html>', encoding="utf-8",
            )
            (root / 'css' / 'nested').mkdir(parents=True)
            (root / 'css' / 'main.css').write_text('@import "nested/theme.css"; #result {color: rgb(12, 34, 56)}', encoding='utf-8')
            (root / 'css' / 'nested' / 'theme.css').write_text(
                '@font-face {font-family:SavedFont;src:url("../../font.ttf")} '
                '#result {font-family:SavedFont} #tile {width:30px;height:30px;background-image:url("../../picture.svg")} '
                '#result::before {content:"保存："}', encoding='utf-8')
            shutil.copyfile('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', root / 'font.ttf')
            (root / 'picture.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="red"/></svg>')
            (root / 'sprite.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><symbol id="icon" viewBox="0 0 20 20"><rect width="20" height="20" fill="blue"/></symbol></svg>')
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                output = root / "output" / "rendered.html"
                save_html(ensure_cloakbrowser().launch, f"http://127.0.0.1:{server.server_port}/index.html", output, wait_seconds=1)
                self.assertIn('<p id="result">罗生门：浏览器渲染成功</p>', output.read_text(encoding="utf-8"))
                report = json.loads(output.with_suffix('.resources.json').read_text(encoding='utf-8'))
                self.assertFalse(report['failed_resources'], report)
                self.assertGreaterEqual(report['embedded_resources'], 4)
                # Double-click equivalent: use file:// in a fresh browser with no network access.
                browser = ensure_cloakbrowser().launch(headless=True)
                try:
                    context = browser.new_context(offline=True)
                    page = context.new_page()
                    requests = []
                    page.on('request', lambda request: requests.append(request.url))
                    page.goto(output.as_uri())
                    page.evaluate('() => document.fonts.ready')
                    self.assertEqual(page.locator('#result').evaluate('(el) => getComputedStyle(el).color'), 'rgb(12, 34, 56)')
                    self.assertEqual(page.locator('#result').evaluate('(el) => getComputedStyle(el, "::before").content'), '"保存："')
                    self.assertTrue(page.locator('#tile').evaluate('(el) => getComputedStyle(el).backgroundImage.includes("data:image/svg+xml")'))
                    for selector in ('#picture', '#responsive'):
                        self.assertTrue(page.locator(selector).evaluate('(el) => el.complete && el.naturalWidth === 20'))
                    self.assertTrue(page.evaluate('() => document.fonts.check("16px SavedFont")'))
                    self.assertEqual(page.locator('svg svg rect').count(), 1)
                    self.assertEqual(page.locator('script').count(), 0)
                    self.assertEqual(page.locator('#video').get_attribute('href'), f'http://127.0.0.1:{server.server_port}/video/123')
                    self.assertFalse([url for url in requests if url.startswith(('http:', 'https:'))], requests)
                    Path('verification').mkdir(exist_ok=True)
                    page.screenshot(path='verification/offline-fixture.png', full_page=True)
                finally:
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
