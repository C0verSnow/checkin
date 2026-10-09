"""Remote-only tests: real browser capture -> real requests -> fixture HTTP API."""

import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import qrcode

from browser_setup import ensure_cloakbrowser
from douyin_export import LoginRecorder
from douyin_login import capture_login
from douyin_requests import run, validate_transaction


class RequestsTests(unittest.TestCase):
    def test_requests_reports_rate_limit_verification_and_unreadable_body_without_retry(self):
        png = BytesIO()
        qrcode.make('https://example.com/response-fixture').save(png, format='PNG')
        cases = [({'code': 0, 'data': {'error_code': 1105, 'description': '验证码发送频繁'}}, 'failed'),
                 ({'data': {'error_code': 0, 'description': '请完成安全验证'}}, 'verification_required'),
                 (None, 'unknown')]
        for payload, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                item = {'url': 'https://sso.douyin.com/passport/web/get_qrcode/',
                        'method': 'GET', 'headers': {}, 'body_base64': ''}
                bundle = root / 'request-bundle.json'
                bundle.write_text(json.dumps({'version': 1, 'qr': item,
                    'sms': dict(item, url='https://sso.douyin.com/passport/web/send_code/', method='POST')}))
                qr = Mock(status_code=200, headers={'Content-Type': 'image/png'}, content=png.getvalue())
                sms = Mock(status_code=200, url='https://sso.douyin.com/passport/web/send_code/')
                if payload is None:
                    sms.json.side_effect = ValueError('SECRET')
                else:
                    sms.json.return_value = payload
                session = Mock()
                session.request.side_effect = [qr, sms]
                # Keep non-sensitive fixture JSON/PNG in the existing CI artifact.
                output = Path('verification/login/requests') / expected
                result = run(bundle, output, True, 5, session=session)
                self.assertEqual(result['status'], expected, result)
                self.assertEqual(result['sms_response_state'], 'completed')
                self.assertEqual(session.request.call_count, 2)
                self.assertTrue(bundle.with_name(bundle.name+'.sms-attempted').exists())
                if payload is None:
                    self.assertEqual(result['sms']['read_error'], 'ValueError')
                if expected == 'failed':
                    self.assertEqual(result['sms']['reason'], 'rate_limited')
                self.assertNotIn('SECRET', (output/'api-result.json').read_text())

    def test_reject_non_douyin_hosts(self):
        for url in ['http://sso.douyin.com/x', 'https://douyin.com.evil.test/x',
                    'https://example.com/x']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_transaction({'url': url, 'method': 'GET'})

    def test_browser_export_and_requests_send_once(self):
        png = BytesIO()
        qrcode.make('https://example.com/api-login-fixture').save(png, format='PNG')
        encoded = base64.b64encode(png.getvalue()).decode()
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('''<meta charset="utf-8"><div><h1>扫码登录</h1><h2>验证码登录</h2></div>
                <img id="qr" width="160" height="160">
                <input id="country" role="combobox" aria-label="国家/地区" aria-owns="select-ul" value="+1"
                    onfocus="document.querySelector('#select-ul').hidden=false"
                    oninput="this.value='+1'">
                <ul id="select-ul" hidden style="list-style:none;padding:0"><li id="areacode_item_0" role="option"
                    onclick="if(event.isTrusted)return;document.querySelector('#country').value='+86'; this.parentElement.hidden=true">
                    <span>中国</span><span>+86</span></li></ul>
                <input placeholder="请输入手机号"><input type="checkbox">
                <button onclick="fetch('/send_code/?signature=fixture', {method:'POST',
                    headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:'mobile=fixture%2Bphone'})">发送验证码</button>
                <script>fetch('/get_qrcode/?signature=fixture').then(r=>r.json()).then(r=>{
                  document.querySelector('#qr').src='data:image/png;base64,'+r.data.qrcode;
                });</script>''', encoding='utf-8')

            class Handler(SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def respond(self, payload):
                    body = json.dumps(payload).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                def do_GET(self):
                    if self.path.startswith('/get_qrcode/'):
                        self.respond({'data': {'qrcode': encoded}})
                    else:
                        super().do_GET()
                def do_POST(self):
                    body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                    calls.append((self.path, body))
                    self.respond({'data': {'error_code': 0, 'description': 'success'}})

            server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                recorder = LoginRecorder()
                report = capture_login(ensure_cloakbrowser().launch, '13657450350', root/'browser',
                    True, 5, headed=True, url=f'http://127.0.0.1:{server.server_port}/index.html', recorder=recorder)
                self.assertEqual(report['status'], 'request_captured', report)
                self.assertTrue(report['qr_saved'])
                self.assertEqual(report['country_selection']['reason'], 'option_clicked')
                self.assertTrue(recorder.qr)
                self.assertTrue(recorder.sms)
                self.assertEqual(calls, [], 'browser must not send SMS')
                bundle = root / 'request-bundle.json'
                recorder.save(bundle)
                self.assertEqual(bundle.stat().st_mode & 0o777, 0o600)
                # Only fixtures can use localhost; production strictly checks Douyin HTTPS.
                with patch('douyin_requests.validate_transaction'):
                    result = run(bundle, root/'api', False, 5)
                    self.assertEqual(result['status'], 'not_requested', result)
                    self.assertEqual(calls, [])
                    result = run(bundle, root/'api', True, 5)
                    self.assertEqual(result['status'], 'request_accepted', result)
                    self.assertEqual(calls, [('/send_code/?signature=fixture', b'mobile=fixture%2Bphone')])
                    result = run(bundle, root/'second', True, 5)
                    self.assertEqual(result['status'], 'error')
                    self.assertEqual(result['error_type'], 'FileExistsError')
                    self.assertEqual(len(calls), 1)
                self.assertTrue((root/'api/api-login-qr.png').read_bytes().startswith(b'\x89PNG'))
                self.assertTrue((root/'api/api-result.png').read_bytes().startswith(b'\x89PNG'))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
