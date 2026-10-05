import importlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import capture_page
import douyin
import bilibili


class CaptureTests(unittest.TestCase):
    def test_existing_package_does_not_install(self):
        module = Mock()
        with patch.object(importlib, "import_module", return_value=module), patch.object(subprocess, "run") as install:
            self.assertIs(capture_page.ensure_cloakbrowser(), module)
            install.assert_not_called()

    def test_missing_package_installs_with_current_python(self):
        module = Mock()
        with patch.object(importlib, "import_module", side_effect=[ModuleNotFoundError(name="cloakbrowser"), module]), patch.object(subprocess, "run") as install:
            self.assertIs(capture_page.ensure_cloakbrowser(), module)
            install.assert_called_once_with([capture_page.sys.executable, "-m", "pip", "install", "cloakbrowser"], check=True)

    def test_broken_dependency_is_not_reinstalled(self):
        with patch.object(importlib, "import_module", side_effect=ModuleNotFoundError(name="playwright")), patch.object(subprocess, "run") as install:
            with self.assertRaises(ModuleNotFoundError):
                capture_page.ensure_cloakbrowser()
            install.assert_not_called()

    def test_each_site_saves_rendered_utf8_and_closes_browser(self):
        for url in (douyin.URL, bilibili.URL):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as directory:
                browser = Mock()
                page = browser.new_page.return_value
                page.url = url
                page.goto.return_value.status = 200
                page.evaluate.return_value = {'html': '<html><head></head><body>罗生门：动态内容</body></html>', 'base': url}
                output = Path(directory) / "nested" / "page.html"
                capture_page.save_html(Mock(return_value=browser), url, output, 30, 2)
                self.assertIn('罗生门：动态内容', output.read_text(encoding="utf-8"))
                self.assertTrue(output.with_suffix('.resources.json').is_file())
                page.goto.assert_called_once_with(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout.assert_called_once_with(2000)
                browser.close.assert_called_once()

    def test_navigation_failure_closes_browser(self):
        browser = Mock()
        browser.new_page.return_value.goto.side_effect = RuntimeError("timeout")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "timeout"):
                capture_page.save_html(Mock(return_value=browser), douyin.URL, Path(directory) / "page.html")
        browser.close.assert_called_once()

    def test_http_error_keeps_diagnostic_html_but_fails(self):
        browser = Mock()
        browser.new_page.return_value.goto.return_value.status = 403
        browser.new_page.return_value.url = bilibili.URL
        browser.new_page.return_value.evaluate.return_value = {'html': '<html><head></head><body>Forbidden</body></html>', 'base': bilibili.URL}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "page.html"
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                capture_page.save_html(Mock(return_value=browser), bilibili.URL, output, wait_seconds=0)
            self.assertTrue(output.is_file())
        browser.close.assert_called_once()

    def test_cli_failure_returns_nonzero(self):
        with patch.object(capture_page.sys, "platform", "linux"), patch.object(capture_page, "ensure_cloakbrowser", side_effect=RuntimeError("pip failed")):
            self.assertEqual(capture_page.main(douyin.URL, "unused.html", []), 1)

    def test_invalid_wait_is_rejected_before_install(self):
        for value in ("-1", "nan", "inf"):
            with self.subTest(value=value), patch.object(capture_page, "ensure_cloakbrowser") as install:
                with self.assertRaises(SystemExit) as error:
                    capture_page.main(douyin.URL, "unused.html", ["--wait-seconds", value])
                self.assertEqual(error.exception.code, 2)
                install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
