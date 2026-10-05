import base64
import unittest
from unittest.mock import Mock

from bs4 import BeautifulSoup
from offline_page import Resources, snapshot


class OfflineTests(unittest.TestCase):
    def test_nested_css_import_font_and_quoted_image(self):
        page = Mock(url='https://example.com/search')
        resources = Resources(page, 1)
        responses = {
            'https://example.com/css/main.css': (b'@import "nested/theme.css"; .x {background:url("../image(1).svg")}', 'text/css', 'https://example.com/css/main.css'),
            'https://example.com/css/nested/theme.css': (b'@font-face {font-family:test;src:url("../../font.woff2")}', 'text/css', 'https://example.com/css/nested/theme.css'),
            'https://example.com/font.woff2': (b'font', 'font/woff2', 'https://example.com/font.woff2'),
            'https://example.com/image(1).svg': (b'<svg/>', 'image/svg+xml', 'https://example.com/image(1).svg'),
        }
        resources.fetch = Mock(side_effect=lambda url: responses[url])
        encoded = resources.embed('/css/main.css', page.url, css=True)
        text = base64.b64decode(encoded.split(',', 1)[1]).decode()
        self.assertIn('data:image/svg+xml;base64,', text)
        self.assertIn('data:text/css;charset=utf-8;base64,', text)
        self.assertEqual(len(resources.cache), 4)
        resources.embed('/css/main.css', page.url, css=True)
        self.assertEqual(resources.fetch.call_count, 4)

    def test_snapshot_removes_restart_scripts_and_keeps_online_links(self):
        page = Mock(url='https://example.com/search')
        page.evaluate.return_value = {'base': 'https://example.com/assets/', 'html': '''
            <html><head><base href="https://example.com/assets/"><meta http-equiv="refresh" content="1">
            <style>.x {color:red}</style></head><body onload="restart()">
            <script>restart()</script><a href="../video/123">视频</a>
            <img src="missing.svg" onerror="restart()"><svg><use href="sprite.svg#icon"></use></svg>
            </body></html>'''}
        def response(url, **kwargs):
            result = Mock(ok=not url.endswith('missing.svg'), status=404, url=url)
            result.body.return_value = b'<svg><symbol id="icon" viewBox="0 0 10 10"><path d="M0 0h10v10z"/></symbol></svg>'
            result.headers = {'content-type': 'image/svg+xml'}
            return result
        page.request.get.side_effect = response
        html, report = snapshot(page)
        soup = BeautifulSoup(html, 'html.parser')
        self.assertFalse(soup.find_all(['script', 'base', 'use']))
        self.assertEqual(soup.a['href'], 'https://example.com/video/123')
        self.assertEqual(soup.meta['charset'], 'utf-8')
        self.assertNotIn('onload', soup.body.attrs)
        self.assertIsNotNone(soup.find('path'))
        self.assertIn('https://example.com/assets/missing.svg', report['failed_resources'])

    def test_circular_stylesheets_stop_and_report(self):
        resources = Resources(Mock(), 1)
        resources.fetch = Mock(return_value=(b'@import "a.css";', 'text/css', 'https://example.com/a.css'))
        self.assertTrue(resources.embed('https://example.com/a.css', '', css=True).startswith('data:'))
        self.assertIn('https://example.com/a.css', resources.failures)


if __name__ == '__main__':
    unittest.main()
