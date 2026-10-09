"""Replay captured Douyin login transactions using requests, without a browser."""

import argparse
import base64
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import requests

from browser_setup import positive_seconds
from douyin_login import summarize_sms_response


def validate_transaction(item):
    if not isinstance(item, dict):
        raise ValueError("没有捕获到对应接口请求，请重新运行 douyin_export.py")
    parts = urlsplit(item["url"])
    if parts.scheme != "https" or not (parts.hostname == "douyin.com" or
                                       (parts.hostname or "").endswith(".douyin.com")):
        raise ValueError("只接受抖音 HTTPS 接口")
    if item["method"] not in {"GET", "POST"}:
        raise ValueError("不支持的请求方法")


def replay(session, item, timeout):
    validate_transaction(item)
    # Preserve signed query strings and the exact encoded body. No automatic retry.
    return session.request(item["method"], item["url"], headers=item["headers"],
                           data=base64.b64decode(item["body_base64"], validate=True),
                           timeout=timeout, allow_redirects=False)


def save_api_qr(response, output):
    from PIL import Image
    import zxingcpp
    if not 200 <= response.status_code < 300:
        raise ValueError("二维码接口没有返回成功 HTTP 状态")
    content_type = response.headers.get("Content-Type", "")
    if content_type.startswith("image/"):
        raw = response.content
    else:
        payload = response.json()
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        encoded = data.get("qrcode") or data.get("qr_code")
        if not isinstance(encoded, str):
            raise ValueError("二维码接口没有返回可保存的二维码图片")
        # Never manufacture a QR from an opaque token or a login URL.
        raw = base64.b64decode(encoded.split(",", 1)[-1], validate=True)
    image = Image.open(BytesIO(raw))
    codes = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)
    if not codes:
        raise ValueError("接口返回的图片无法解码为二维码")
    image.save(output / "api-login-qr.png", format="PNG")


def save_result_png(report, output):
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (1000, 360), "white")
    draw = ImageDraw.Draw(image)
    lines = ["Douyin requests API result (not a browser screenshot)",
             "UTC: " + report["time_utc"], "QR saved from API: " + str(report["qr_saved"]),
             "SMS request attempted: " + str(report["sms_attempted"]),
             "Status: " + report["status"], "HTTP: " + str(report.get("sms", {}).get("http_status", "-")),
             "Server code: " + str(report.get("sms", {}).get("code", "-")),
             "Server acceptance does not prove delivery to the phone."]
    for index, line in enumerate(lines):
        draw.text((24, 24 + index * 36), line, fill="black")
    image.save(output / "api-result.png")


def run(bundle_path, output, send_code=False, timeout=60, session=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("api-login-qr.png", "api-result.png", "api-result.json"):
        (output / name).unlink(missing_ok=True)
    report = {"time_utc": datetime.now(timezone.utc).isoformat(), "qr_saved": False,
              "sms_attempted": False, "status": "error"}
    own_session = session is None
    session = session or requests.Session()
    try:
        bundle_path = Path(bundle_path)
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        if bundle.get("version") != 1:
            raise ValueError("不支持的请求文件版本")
        qr_response = replay(session, bundle.get("qr"), timeout)
        report["qr_http_status"] = qr_response.status_code
        report["qr_content_type"] = qr_response.headers.get("Content-Type", "")
        if "json" in report["qr_content_type"]:
            payload = qr_response.json()
            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            if isinstance(data, dict):
                report["qr_data_fields"] = sorted(data)
        save_api_qr(qr_response, output)
        report["qr_saved"] = True
        report["status"] = "not_requested"
        if send_code:
            validate_transaction(bundle.get("sms"))
            if bundle["sms"]["method"] != "POST":
                raise ValueError("短信请求必须是 POST")
            from douyin_login import sms_endpoint
            if not sms_endpoint(bundle["sms"]["url"]):
                raise ValueError("请求不是短信发送接口")
            # A persistent exclusive marker prevents rerunning the same bundle,
            # even after timeouts, failures, or a simultaneous second process.
            marker = bundle_path.with_name(bundle_path.name + ".sms-attempted")
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            report["sms_attempted"] = True
            response = replay(session, bundle["sms"], timeout)
            class Adapter:
                url = response.url
                status = response.status_code
                def json(self):
                    return response.json()
            report["sms"] = summarize_sms_response(Adapter())
            report["status"] = report["sms"]["status"]
    except Exception as exc:
        # Exception messages may include signed URLs: never print them.
        report["status"] = "error"
        report["error_type"] = type(exc).__name__
    finally:
        if own_session:
            session.close()
        (output / "api-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        save_result_png(report, output)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="直接用 requests 调用捕获的抖音接口，保存二维码并可选发送一次短信")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output/douyin-api"))
    parser.add_argument("--send-code", action="store_true")
    parser.add_argument("--timeout-seconds", type=positive_seconds, default=60)
    args = parser.parse_args(argv)
    report = run(args.bundle, args.output_dir, args.send_code, args.timeout_seconds)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["qr_saved"] and report["status"] in {"not_requested", "request_accepted"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
