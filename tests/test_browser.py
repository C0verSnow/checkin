"""Remote Linux integration: real CloakBrowser renders JavaScript and saves HTML."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from capture_page import ensure_cloakbrowser, save_html


class BrowserIntegrationTests(unittest.TestCase):
    def test_real_browser_saves_javascript_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text(
                '<html><meta charset="utf-8"><body><p id="result">加载中</p>'
                '<script>setTimeout(() => {document.querySelector("#result").textContent = '
                '"罗生门：浏览器渲染成功";}, 100);</script></body></html>', encoding="utf-8",
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                output = root / "output" / "rendered.html"
                save_html(ensure_cloakbrowser().launch, f"http://127.0.0.1:{server.server_port}/index.html", output, wait_seconds=1)
                self.assertIn('<p id="result">罗生门：浏览器渲染成功</p>', output.read_text(encoding="utf-8"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
