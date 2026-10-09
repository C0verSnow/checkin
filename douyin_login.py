"""Capture Douyin's login QR and the result of one SMS request with CloakBrowser."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

from browser_setup import ensure_cloakbrowser, positive_seconds

URL = "https://www.douyin.com/"
DEFAULT_PHONE = "13657450350"
SEND_TEXT = re.compile(r"^(发送验证码|获取验证码)$")
QR_SELECTOR = 'img, canvas, div'


def visible(locator):
    """Choose a visible match rather than a hidden copy of the login form."""
    for index in range(locator.count()):
        candidate = locator.nth(index)
        if candidate.is_visible():
            return candidate
    return None


def phone_field(page):
    return visible(page.get_by_placeholder(re.compile("手机号|手机号码")))


def select_china_country(page):
    """Edit the country input directly; there is no dropdown selection step."""
    country = visible(page.get_by_role("combobox", name="国家/地区", exact=True))
    if country is None:
        country = visible(page.locator('input[name="web-login-area-code-input"]'))
    if country is None:
        raise RuntimeError("没有找到可编辑的手机号区号输入框")
    country.fill("+86")
    country.press("Tab")
    if country.input_value().strip() != "+86":
        raise RuntimeError("区号没有改成 +86，停止发送")
    return country


def open_login(page):
    if phone_field(page) is not None or visible(page.get_by_text("扫码登录", exact=True)) is not None:
        return
    button = visible(page.get_by_role("button", name="登录", exact=True))
    if button is None:
        button = visible(page.get_by_text("登录", exact=True))
    if button is None:
        raise RuntimeError("没有找到登录入口")
    try:
        button.click(timeout=5000)
    except Exception:
        # Douyin can open its login panel while the entry click is waiting.
        # That panel intercepts the entry button; use the panel already open.
        if phone_field(page) is None and visible(page.get_by_text("扫码登录", exact=True)) is None:
            raise
    page.get_by_text(re.compile("扫码登录|验证码登录|手机号登录")).first.wait_for()


def save_qr(page, output, timeout_seconds):
    # Decode candidates inside the login panel; image URLs need not mention QR.
    from io import BytesIO
    from PIL import Image
    import zxingcpp

    page.screenshot(path=str(output / "login.png"), full_page=True)
    heading = visible(page.get_by_text("扫码登录", exact=True))
    if heading is None:
        tab = visible(page.get_by_text("二维码登录", exact=True))
        if tab is not None:
            tab.click()
            heading = visible(page.get_by_text("扫码登录", exact=True))
    if heading is None:
        raise RuntimeError("没有找到扫码登录区域")
    panel = heading.locator("xpath=ancestor::*[contains(., '验证码登录')][1]")
    if not panel.count():
        raise RuntimeError("没有找到同时包含扫码和验证码登录的弹窗")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        candidates = panel.locator(QR_SELECTOR)
        for index in range(candidates.count()):
            candidate = candidates.nth(index)
            if not candidate.is_visible():
                continue
            box = candidate.bounding_box()
            if not box or not (100 <= box["width"] <= 320 and 100 <= box["height"] <= 320):
                continue
            if not 0.8 <= box["width"] / box["height"] <= 1.2:
                continue
            png = candidate.screenshot(timeout=5000)
            codes = zxingcpp.read_barcodes(Image.open(BytesIO(png)), formats=zxingcpp.BarcodeFormat.QRCode)
            if codes:
                (output / "login-qr.png").write_bytes(png)
                page.screenshot(path=str(output / "login.png"), full_page=True)
                return
        page.wait_for_timeout(250)
    raise RuntimeError("登录二维码没有加载出来或无法解码，已保存登录页面")


def sms_result(text, button_text=""):
    """Only explicit sent feedback counts; a countdown alone is inconclusive."""
    if re.search(r"验证码发送失败|发送失败|操作频繁|频繁操作|稍后再试|请求失败|手机号.{0,8}(错误|不正确|无效)", text):
        return "failed"
    if re.search(r"请.{0,8}(完成|进行).{0,8}验证|拖动.{0,12}(滑块|拼图)|安全验证|请依次点击", text):
        return "verification_required"
    if re.search(r"验证码已发送|验证码发送成功|发送验证码成功|短信.{0,6}(已发送|发送成功)|已发送.{0,12}(手机|短信)", text):
        return "sent"
    if re.search(r"\d+\s*(秒|s|S)|重新发送|重新获取", button_text):
        return "countdown_only"
    return "unknown"


def sms_endpoint(url):
    return bool(re.search(r"send[_/-]?(?:activation[_/-]?|verification[_/-]?)?(?:code|sms)|sms[/_-]send", urlsplit(url).path, re.I))


def summarize_sms_response(response):
    """Keep only outcome fields, never cookies, response tokens or URL queries."""
    endpoint = urlsplit(response.url)
    summary = {"endpoint": endpoint.scheme + "://" + endpoint.netloc + endpoint.path,
               "http_status": response.status, "status": "unknown"}
    try:
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("短信接口没有返回 JSON 对象")
        data = payload.get("data")
        data = data if isinstance(data, dict) else {}
        for key in ("error_code", "status_code", "code"):
            value = data.get(key, payload.get(key))
            if value is not None:
                summary["code"] = value
                break
        message = data.get("description") or data.get("message") or payload.get("description") or payload.get("message") or ""
        summary["message"] = str(message)[:300]
        if data.get("verify_center_decision_conf"):
            summary["status"] = "verification_required"
        elif response.status >= 400:
            summary["status"] = "failed"
        elif type(summary.get("code")) is int and summary["code"] == 0 and 200 <= response.status < 300:
            summary["status"] = "request_accepted"
        elif re.search(r"安全验证|完成验证|滑块|captcha|verification|verify", summary["message"], re.I):
            summary["status"] = "verification_required"
        elif "code" in summary and summary["code"] not in (0, "0"):
            summary["status"] = "failed"
    except Exception as exc:
        summary["read_error"] = type(exc).__name__
        if response.status >= 400:
            summary["status"] = "failed"
    return summary


def visible_feedback(page):
    text = page.locator("body").inner_text()
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            if frame.frame_element().is_visible():
                text += "\n" + frame.locator("body").inner_text(timeout=500)
        except Exception:
            # Detached or unloaded frames cannot provide feedback.
            continue
    return text


def capture_login(launch, phone, output, send_code=False, timeout_seconds=60, headed=False, url=URL, recorder=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Remove old evidence so a failed run cannot inherit a successful screenshot.
    for name in ("login.png", "login-qr.png", "before-send.png", "after-click.png", "sms-result.png", "result.json"):
        (output / name).unlink(missing_ok=True)
    report = {"time_utc": datetime.now(timezone.utc).isoformat(), "phone": phone,
              "status": "not_requested", "send_attempted": False, "send_clicked": False, "qr_saved": False, "sms_responses": []}
    browser = None
    page = None
    try:
        browser = launch(headless=not headed, locale="zh-CN", timezone="Asia/Shanghai",
                         humanize=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        if recorder is not None:
            recorder.attach(page)
        page.set_default_timeout(timeout_seconds * 1000)
        response = page.goto(url, wait_until="domcontentloaded")
        if response is None or response.status >= 400:
            raise RuntimeError(f"页面导航失败：HTTP {response.status if response else '无响应'}")
        page.wait_for_timeout(5000)
        open_login(page)
        save_qr(page, output, timeout_seconds)
        report["qr_saved"] = True
        field = phone_field(page)
        if field is None:
            tab = visible(page.get_by_text(re.compile(r"^(验证码登录|手机号登录|短信登录)$")))
            if tab is None:
                raise RuntimeError("没有找到手机号登录入口")
            tab.click()
            page.get_by_placeholder(re.compile("手机号|手机号码")).first.wait_for()
            field = phone_field(page)
        if field is None:
            raise RuntimeError("没有找到手机号输入框")
        country = select_china_country(page)
        report["country_code"] = "+86"
        field.fill(phone)
        if country.input_value().strip() != "+86":
            raise RuntimeError("填写手机号后区号发生变化，停止发送")
        # Agree to the login terms only in the visible phone form when required.
        checkbox = visible(page.get_by_role("checkbox"))
        if checkbox is not None and not checkbox.is_checked():
            checkbox.check()
        send = visible(page.get_by_text(SEND_TEXT, exact=True))
        if send is None:
            raise RuntimeError("没有找到发送验证码按钮")
        page.screenshot(path=str(output / "before-send.png"), full_page=True)
        if send_code:
            def on_response(response):
                if sms_endpoint(response.url) and response.request.method == "POST":
                    report["sms_responses"].append(summarize_sms_response(response))
            page.on("response", on_response)
            send.scroll_into_view_if_needed()
            report["send_button_box"] = send.bounding_box()
            if report["send_button_box"] is None:
                raise RuntimeError("发送按钮没有可见位置")
            send.evaluate("""el => {
                const root = document.documentElement;
                delete root.dataset.checkinSendClick;
                delete root.dataset.checkinSendPointer;
                const matched = event => el === event.target || el.contains(event.target)
                    || /^(发送验证码|获取验证码)$/.test((event.target.textContent || '').trim());
                window.addEventListener('pointerdown', event => {
                    root.dataset.checkinSendPointer = JSON.stringify({trusted: event.isTrusted,
                        matched: matched(event), x: event.clientX, y: event.clientY});
                }, {capture: true, once: true});
                window.addEventListener('click', event => {
                    root.dataset.checkinSendClick = JSON.stringify({trusted: event.isTrusted,
                        matched: matched(event), x: event.clientX, y: event.clientY,
                        target_text: (event.target.textContent || '').trim().slice(0, 100)});
                }, {capture: true, once: true});
            }""")
            # Exactly one click; do not retry SMS requests on ambiguous feedback.
            report["send_attempted"] = True
            box = report["send_button_box"]
            # Click the screenshot-visible center directly rather than relying
            # on the locator's content-quad coordinate conversion.
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            clicked_at = time.monotonic()
            page.wait_for_timeout(250)
            page.screenshot(path=str(output / "after-click.png"), full_page=True)
            # DOM attributes are shared even when the browser isolates JS worlds.
            html = page.locator("html")
            report["click_event"] = json.loads(html.get_attribute("data-checkin-send-click") or "null")
            report["pointer_event"] = json.loads(html.get_attribute("data-checkin-send-pointer") or "null")
            report["send_clicked"] = True  # The browser click action completed.
            report["click_event_confirmed"] = bool(report["click_event"] and report["click_event"]["matched"] and report["click_event"]["trusted"])
            # A site can suppress diagnostic listeners; still observe this one
            # action's UI and server response instead of closing too early.
            report["status"] = "unknown"
            deadline = clicked_at + timeout_seconds
            while time.monotonic() < deadline:
                if recorder is not None and recorder.sms is not None:
                    report["status"] = "request_captured"
                    break
                text = visible_feedback(page)
                feedback_button = visible(page.get_by_text(re.compile(r"\d+\s*(秒|s|S).{0,12}|重新发送|重新获取")))
                button_text = feedback_button.inner_text() if feedback_button is not None else ""
                status = sms_result(text, button_text)
                if status not in {"sent", "failed", "verification_required"}:
                    for result in report["sms_responses"]:
                        if result["status"] != "unknown":
                            status = result["status"]
                            if status in {"failed", "verification_required"}:
                                break
                report.update(status=status, feedback_text=text, button_text=button_text)
                if status in {"sent", "failed", "verification_required"}:
                    break
                if status == "request_accepted" and time.monotonic() - clicked_at >= 2:
                    break
                page.wait_for_timeout(250)
        return report
    except Exception as exc:
        report.update(status="error", error=str(exc))
        return report
    finally:
        try:
            if page is not None:
                report["url"] = page.url
                report["page_text"] = page.locator("body").inner_text()
                if report["status"] == "error":
                    report["form_controls"] = page.locator("input").evaluate_all(
                        "els => els.map(el => ({type:el.type, value:el.value, placeholder:el.placeholder, html:el.outerHTML.slice(0,1500)}))")
                page.screenshot(path=str(output / "sms-result.png"), full_page=True)
        except Exception as exc:
            report["screenshot_error"] = str(exc)
            report["status"] = "error"
        finally:
            (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            if browser is not None:
                browser.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="用 CloakBrowser 保存抖音登录二维码与验证码发送结果")
    parser.add_argument("--phone", default=DEFAULT_PHONE)
    parser.add_argument("--output-dir", type=Path, default=Path("output/douyin-login"))
    parser.add_argument("--send-code", action="store_true", help="点击一次发送验证码；不加此参数只截图")
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口，需要桌面环境")
    parser.add_argument("--timeout-seconds", type=positive_seconds, default=60)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"1\d{10}", args.phone):
        parser.error("手机号应为 11 位数字，以 1 开头")
    try:
        report = capture_login(ensure_cloakbrowser().launch, args.phone, args.output_dir,
                               args.send_code, args.timeout_seconds, args.headed)
    except Exception as exc:
        print(f"浏览器准备失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: value for key, value in report.items() if key not in {"page_text", "feedback_text", "form_controls"}}, ensure_ascii=False, indent=2))
    print(f"截图和报告：{args.output_dir.resolve()}")
    return 0 if report["qr_saved"] and report["status"] in {"sent", "request_accepted", "not_requested"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
