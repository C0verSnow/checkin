"""Remote CI: business outcomes and request lifecycle, without real SMS."""

import json
import unittest
from unittest.mock import Mock

from douyin_login import observe_sms_requests, summarize_sms_response, type_input


class SmsResponseTests(unittest.TestCase):
    def test_input_must_receive_focus_before_any_keyboard_action(self):
        page = Mock()
        field = Mock()
        field.evaluate.return_value = False
        with self.assertRaisesRegex(RuntimeError, '没有获得焦点'):
            type_input(page, field, '+86')
        page._original.keyboard_press.assert_not_called()
        page._original.keyboard_type.assert_not_called()
        field.focus.assert_not_called()

    def test_business_errors_override_success_and_sensitive_fields_are_not_saved(self):
        cases = [
            ({'data': {'error_code': '0'}}, 200, 'request_accepted', 0),
            ({'code': 0, 'data': {'error_code': 1105, 'description': '验证码发送频繁'}}, 200, 'failed', 1105),
            ({'code': 12, 'data': {'error_code': 0}}, 200, 'failed', 12),
            ({'data': {'error_code': 0, 'description': '请完成安全验证'}}, 200, 'verification_required', 0),
            ({'code': 0, 'verify_center_decision_conf': {'token': 'SECRET'}}, 200, 'verification_required', 0),
            ({'data': {'code': 0}, 'message': '验证码发送频繁'}, 200, 'failed', 0),
            ({'data': {'code': 0}, 'message': '发送失败'}, 200, 'failed', 0),
            ({'message': 'success'}, 200, 'unknown', None),
            ({'code': False}, 200, 'unknown', None),
            ({'code': 'nonsense'}, 200, 'unknown', None),
            ({'data': None}, 200, 'unknown', None),
            ({'data': {'code': 0}}, 503, 'failed', 0),
            ({'message': 'Too many requests'}, 429, 'failed', None),
            ([], 200, 'unknown', None),
        ]
        for payload, http_status, status, code in cases:
            with self.subTest(payload=payload, http_status=http_status):
                response = Mock(url='https://sso.douyin.com/passport/web/send_code/?signature=SECRET', status=http_status)
                if isinstance(payload, dict):
                    payload = dict(payload, token='SECRET', cookie='SECRET')
                response.json.return_value = payload
                result = summarize_sms_response(response)
                self.assertEqual(result['status'], status)
                self.assertEqual(result.get('code'), code)
                self.assertNotIn('SECRET', json.dumps(result))

    def test_unreadable_response_does_not_hide_http_failure(self):
        for http_status, expected in [(200, 'unknown'), (429, 'failed'), (502, 'failed')]:
            response = Mock(url='https://sso.douyin.com/send_code/', status=http_status)
            response.json.side_effect = ValueError('body contains SECRET')
            result = summarize_sms_response(response)
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['read_error'], 'ValueError')
            self.assertNotIn('SECRET', json.dumps(result))
            if http_status == 429:
                self.assertEqual(result['reason'], 'rate_limited')

    def test_observer_reads_finished_bodies_and_distinguishes_aborts(self):
        for recorder, failed_state in [(None, 'network_error'), (Mock(), 'blocked')]:
            page = Mock()
            report = {'send_attempted': False, 'sms_responses': []}
            pending = observe_sms_requests(page, report, recorder)
            handlers = {call.args[0]: call.args[1] for call in page.context.on.call_args_list}
            request = Mock(url='https://sso.douyin.com/send_code/?signature=SECRET', method='POST')
            # Ignore background traffic and CORS preflight.
            handlers['request'](request)
            self.assertEqual(pending, {})
            report['send_attempted'] = True
            handlers['request'](Mock(url=request.url, method='OPTIONS'))
            self.assertEqual(pending, {})
            handlers['request'](request)
            self.assertIn(request, pending)
            request.response.assert_not_called()
            response = Mock(url=request.url, status=200)
            response.json.return_value = {'data': {'error_code': 0}}
            request.response.return_value = response
            handlers['requestfinished'](request)
            self.assertEqual(pending, {})
            self.assertEqual(report['sms_responses'][0]['status'], 'request_accepted')
            handlers['request'](request)
            handlers['requestfailed'](request)
            self.assertEqual(pending, {})
            self.assertEqual(report['sms_requests'][-1]['state'], failed_state)
            self.assertEqual(len(report['sms_responses']), 1)
            self.assertNotIn('SECRET', json.dumps(report))


if __name__ == '__main__':
    unittest.main()
