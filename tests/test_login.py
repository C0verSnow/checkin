"""Run only on remote CI: verify SMS outcomes and one-click behavior in CloakBrowser."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import qrcode
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from pathlib import Path
import tempfile
import threading
import unittest

from capture_page import ensure_cloakbrowser
from douyin_login import capture_login, open_login, sms_result, sms_endpoint, summarize_sms_response


class LoginTests(unittest.TestCase):
    def test_auto_opened_panel_during_entry_click(self):
        page = Mock()
        button = Mock()
        button.click.side_effect = RuntimeError('login panel intercepts pointer events')
        with patch('douyin_login.phone_field', side_effect=[None, Mock()]), \
             patch('douyin_login.visible', side_effect=[None, button]):
            open_login(page)
        button.click.assert_called_once_with(timeout=5000)
        with patch('douyin_login.phone_field', return_value=None), \
             patch('douyin_login.visible', side_effect=[None, button, None]):
            with self.assertRaisesRegex(RuntimeError, 'intercepts'):
                open_login(page)

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

    def test_server_response_does_not_confuse_http_200_with_success(self):
        response = Mock(url='https://sso.douyin.com/passport/web/send_code/?token=secret', status=200)
        response.json.return_value = {'message': 'success'}
        self.assertEqual(summarize_sms_response(response)['status'], 'unknown')
        response.json.return_value = {'data': {'error_code': 0, 'description': '验证码发送成功', 'token': 'secret'}}
        result = summarize_sms_response(response)
        self.assertEqual(result['status'], 'request_accepted')
        self.assertNotIn('secret', json.dumps(result))
        response.json.return_value = {'data': {'error_code': 12, 'description': '请完成安全验证'}}
        self.assertEqual(summarize_sms_response(response)['status'], 'verification_required')
        response.json.return_value = {'data': {'error_code': 12, 'description': '发送失败'}}
        self.assertEqual(summarize_sms_response(response)['status'], 'failed')
        response.status = 500
        response.json.side_effect = ValueError('not JSON')
        self.assertEqual(summarize_sms_response(response)['status'], 'failed')
        self.assertTrue(sms_endpoint(response.url))
        self.assertFalse(sms_endpoint('https://sso.douyin.com/passport/web/get_qrcode/'))

    def test_real_browser_qr_phone_single_click_and_failed_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # A real, decodable test QR containing no login credential.
            qrcode.make('https://example.com/login-fixture').save(root / 'image.png')
            (root / 'index.html').write_text('''<meta charset="utf-8"><h1>扫码登录</h1>
                <img src="image.png" width="160" height="160"><h2>验证码登录</h2>
                <div><input role="combobox" aria-label="国家/地区" name="web-login-area-code-input" id="country" value="+1">
                <input placeholder="请输入手机号"></div><input type="checkbox" aria-label="同意协议">
                <button onclick="if (!document.querySelector('input[type=checkbox]').checked || document.querySelector('#country').value !== '+86') return;
                window.clicks++; this.textContent='59秒后重新发送';
                const outcome=new URLSearchParams(location.search).get('feedback');
                if (outcome==='iframe') {
                    const frame=document.createElement('iframe'); frame.srcdoc='<p>请完成安全验证</p>'; document.body.append(frame);
                } else if (!outcome.startsWith('api_')) document.querySelector('#feedback').textContent=outcome;
                fetch('/send_code/?outcome='+encodeURIComponent(outcome), {method:'POST'});">发送验证码</button>
                <div id="feedback"></div><script>window.clicks=0;</script>''', encoding='utf-8')
            class Handler(SimpleHTTPRequestHandler):
                def do_POST(self):
                    outcome = parse_qs(urlsplit(self.path).query).get('outcome', [''])[0]
                    payload = {'data': {'error_code': 0}} if outcome == 'api_accepted' else {}
                    if outcome == 'api_rejected':
                        payload = {'data': {'error_code': 12, 'description': '发送失败'}}
                    body = json.dumps(payload).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            browser_launch = ensure_cloakbrowser().launch
            try:
                for feedback, expected in [('验证码已发送', 'sent'), ('验证码发送失败', 'failed'), ('请完成安全验证', 'verification_required'), ('等待反馈', 'countdown_only'), ('api_accepted', 'request_accepted'), ('api_rejected', 'failed'), ('iframe', 'verification_required')]:
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
                                evidence['country'] = self.page.locator('#country').input_value()
                                self.browser.close()
                        def wrapped_launch(**kwargs):
                            return WrappedBrowser(launch(**kwargs))
                        output = Path('verification/login') / feedback
                        report = capture_login(wrapped_launch, '13657450350', output, True, 4,
                            url=f'http://127.0.0.1:{server.server_port}/index.html?{urlencode({"feedback": feedback})}')
                        self.assertEqual(report['status'], expected, report)
                        self.assertTrue(report['qr_saved'])
                        self.assertTrue(report['send_clicked'], report)
                        self.assertEqual(evidence, {'clicks': 1, 'phone': '13657450350', 'country': '+86'})
                        self.assertEqual(json.loads((output/'result.json').read_text())['status'], expected)
                        for name in ('login-qr.png', 'before-send.png', 'after-click.png', 'sms-result.png'):
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
