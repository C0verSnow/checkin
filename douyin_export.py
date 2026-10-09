"""Record actual signed login requests and browser SMS responses without interception."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from browser_setup import ensure_cloakbrowser, positive_seconds
from douyin_login import capture_login, sms_endpoint


def transaction(request):
    headers = request.all_headers()
    # requests computes transport headers for the captured bytes itself.
    headers = {k: v for k, v in headers.items() if k.lower() not in
               {"host", "content-length", "connection", "accept-encoding"} and not k.startswith(":")}
    body = request.post_data_buffer
    import base64
    return {"url": request.url, "method": request.method, "headers": headers,
            "body_base64": base64.b64encode(body or b"").decode("ascii")}


class LoginRecorder:
    def __init__(self):
        self.sms = None
        self.qr = None
        self.sms_attempted = False
        self.errors = []

    def attach(self, page):
        def request_sent(request):
            if sms_endpoint(request.url) and request.method == "POST":
                # Mark attempted before reading private request data. A failed
                # capture or network error must never permit a second send.
                self.sms_attempted = True
                try:
                    if self.sms is None:
                        self.sms = transaction(request)
                except Exception as exc:
                    self.errors.append(type(exc).__name__)

        def response_received(response):
            if "get_qrcode" in urlsplit(response.url).path:
                try:
                    self.qr = transaction(response.request)
                except Exception as exc:
                    self.errors.append(type(exc).__name__)

        page.context.on("request", request_sent)
        page.on("response", response_received)

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Full signed URLs and cookies are private input, never console output.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.chmod(path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"version": 1, "qr": self.qr, "sms": self.sms,
                       "sms_attempted": self.sms_attempted}, stream, ensure_ascii=False, indent=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description="记录抖音登录请求和浏览器短信返回，供 requests 验证二维码")
    parser.add_argument("--phone", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output/douyin-api"))
    parser.add_argument("--send-code", "--capture-sms", dest="send_code", action="store_true",
                        help="浏览器点击一次实际发送短信并记录返回，不拦截；旧参数 --capture-sms 含义相同")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-seconds", type=positive_seconds, default=60)
    args = parser.parse_args(argv)
    import re
    if not re.fullmatch(r"1\d{10}", args.phone):
        parser.error("手机号应为 11 位数字，以 1 开头")
    bundle = args.output_dir / "request-bundle.json"
    bundle.unlink(missing_ok=True)
    recorder = LoginRecorder()
    report = capture_login(ensure_cloakbrowser().launch, args.phone, args.output_dir,
                           args.send_code, args.timeout_seconds, args.headed, recorder=recorder)
    recorder.save(bundle)
    result = {"qr_request_captured": recorder.qr is not None,
              "sms_request_captured": recorder.sms is not None,
              "browser_sms_attempted": recorder.sms_attempted,
              "browser_status": report["status"], "capture_errors": recorder.errors}
    (args.output_dir / "export-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    expected_status = "request_accepted" if args.send_code else "not_requested"
    return 0 if (report["status"] == expected_status and report["qr_saved"] and recorder.qr
                 and (not args.send_code or recorder.sms)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
