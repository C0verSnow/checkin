"""Export actual signed login requests; browser SMS traffic is always aborted."""

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
        self.blocked_sms = 0
        self.errors = []

    def attach(self, page):
        def route_request(route):
            request = route.request
            if sms_endpoint(request.url):
                # Block every matching request, including automatic page retries.
                self.blocked_sms += 1
                try:
                    if self.sms is None and request.method == "POST":
                        self.sms = transaction(request)
                except Exception as exc:
                    self.errors.append(type(exc).__name__)
                finally:
                    route.abort()
            else:
                route.continue_()

        def response_received(response):
            if "get_qrcode" in urlsplit(response.url).path:
                try:
                    self.qr = transaction(response.request)
                except Exception as exc:
                    self.errors.append(type(exc).__name__)

        page.context.route("**/*", route_request)
        page.on("response", response_received)

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Full signed URLs and cookies are private input, never console output.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.chmod(path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"version": 1, "qr": self.qr, "sms": self.sms,
                       "sms_attempted": False}, stream, ensure_ascii=False, indent=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description="捕获抖音登录请求，拦截浏览器短信请求，供 requests 重放")
    parser.add_argument("--phone", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output/douyin-api"))
    parser.add_argument("--capture-sms", action="store_true", help="点击一次以捕获请求，浏览器请求会被拦截")
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
                           args.capture_sms, args.timeout_seconds, args.headed, recorder=recorder)
    recorder.save(bundle)
    result = {"qr_request_captured": recorder.qr is not None,
              "sms_request_captured": recorder.sms is not None,
              "blocked_browser_sms": recorder.blocked_sms,
              "browser_status": report["status"], "capture_errors": recorder.errors}
    (args.output_dir / "export-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    expected_status = "request_captured" if args.capture_sms else "not_requested"
    return 0 if (report["status"] == expected_status and report["qr_saved"] and recorder.qr
                 and (not args.capture_sms or recorder.sms)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
