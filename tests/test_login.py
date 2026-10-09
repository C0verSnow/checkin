"""Run only on remote CI: verify SMS outcomes and one-click behavior in CloakBrowser."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import qrcode
from pathlib import Path
import tempfile
import threading
import unittest

from capture_page import ensure_cloakbrowser
from douyin_login import capture_login, sms_result


class LoginTests(unittest.TestCase):
    def test_feedback_requires_explicit_success(self):
        for text, button, expected in [
            ('验证码已发送', '59秒后重新发送', 'sent'),
            ('验证码发送失败，请稍后再试', '59秒', 'failed'),
            ('请完成安全验证', '59秒', 'verification_required'),
            ('验证码登录', '59秒后重新发送', 'countdown_only'),
            ('验证码登录', '发送验证码', 'unknown'),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(sms_result(text, button), expected)

    def test_real_browser_qr_phone_single_click_and_failed_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # A real, decodable test QR containing no login credential.
            qrcode.make('https://example.com/login-fixture').save(root / 'image.png')
            (root / 'index.html').write_text('''<meta charset="utf-8"><h1>扫码登录</h1>
                <img src="image.png" width="160" height="160"><h2>验证码登录</h2>
                <div><button id="country" onclick="document.querySelector('#countries').hidden=false">+1</button>
                <div id="countries" hidden><span onclick="document.querySelector('#country').textContent='+86'; document.querySelector('#countries').hidden=true">+86</span></div>
                <input placeholder="请输入手机号"></div><input type="checkbox" aria-label="同意协议">
                <button onclick="if (!document.querySelector('input[type=checkbox]').checked) return;
                window.clicks++; this.textContent='59秒后重新发送';
                document.querySelector('#feedback').textContent=new URLSearchParams(location.search).get('feedback');">发送验证码</button>
                <div id="feedback"></div><script>window.clicks=0;</script>''', encoding='utf-8')
            server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            browser_launch = ensure_cloakbrowser().launch
            try:
                for feedback, expected in [('验证码已发送', 'sent'), ('验证码发送失败', 'failed'), ('请完成安全验证', 'verification_required'), ('等待反馈', 'countdown_only')]:
                    with self.subTest(expected=expected):
                        from urllib.parse import urlencode
                        def launch(**kwargs):
                            browser = browser_launch(**kwargs)
                            return browser
                        # Capture actual inputs and click count immediately before close.
                        evidence = {}
                        class WrappedBrowser:
                            def __init__(self, browser):
                                self.browser = browser
                            def new_page(self, **kwargs):
                                self.page = self.browser.new_page(**kwargs)
                                return self.page
                            def close(self):
                                evidence['clicks'] = self.page.evaluate('window.clicks')
                                evidence['phone'] = self.page.locator('input[placeholder]').input_value()
                                evidence['country'] = self.page.locator('#country').inner_text()
                                self.browser.close()
                        def wrapped_launch(**kwargs):
                            return WrappedBrowser(launch(**kwargs))
                        output = Path('verification/login') / expected
                        report = capture_login(wrapped_launch, '13657450350', output, True, 2,
                            url=f'http://127.0.0.1:{server.server_port}/index.html?{urlencode({"feedback": feedback})}')
                        self.assertEqual(report['status'], expected, report)
                        self.assertTrue(report['qr_saved'])
                        self.assertEqual(evidence, {'clicks': 1, 'phone': '13657450350', 'country': '+86'})
                        self.assertEqual(json.loads((output/'result.json').read_text())['status'], expected)
                        for name in ('login-qr.png', 'before-send.png', 'sms-result.png'):
                            self.assertTrue((output/name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
                output = Path('verification/login/no-send')
                report = capture_login(wrapped_launch, '13657450350', output, False, 2,
                    url=f'http://127.0.0.1:{server.server_port}/index.html')
                self.assertEqual(report['status'], 'not_requested', report)
                self.assertEqual(evidence['clicks'], 0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
