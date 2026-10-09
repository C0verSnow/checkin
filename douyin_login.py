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
COUNTRY_CODE = "+1"
SEND_TEXT = re.compile(r"^(发送验证码|获取验证码)$")
QR_SELECTOR = 'img, canvas, div'
DOM_HELPERS = Path(__file__).with_name("douyin_dom.js").read_text(encoding="utf-8")


def visible(locator):
    """Choose a visible match rather than a hidden copy of the login form."""
    for index in range(locator.count()):
        candidate = locator.nth(index)
        if candidate.is_visible():
            return candidate
    return None


def phone_field(page):
    return visible(page.get_by_placeholder(re.compile("手机号|手机号码")))


def type_input(page, field, value):
    """Focus the actual input without humanized locator click coordinates."""
    # CloakBrowser also patches Locator.focus; use the DOM input itself so
    # focusing cannot turn into another coordinate-based mouse action.
    focused = field.evaluate("el => (" + DOM_HELPERS + ").focusInput(el)")
    if not focused:
        raise RuntimeError("输入框没有获得焦点，停止发送")
    original = getattr(page, "_original", None)
    if original is not None:
        original.keyboard_press("ControlOrMeta+A")
        original.keyboard_type(value, delay=80)
    else:
        page.keyboard.press("ControlOrMeta+A")
        page.keyboard.type(value, delay=80)
    if field.input_value() != value:
        raise RuntimeError("输入框的内容和预期不一致，停止发送")


def edit_country_code(page, report=None):
    """Edit the visible country input and verify it survives losing focus."""
    country = visible(page.get_by_role("combobox", name="国家/地区", exact=True))
    if country is None:
        country = visible(page.locator('input[name="web-login-area-code-input"]'))
    if country is None:
        raise RuntimeError("没有找到可编辑的手机号区号输入框")
    type_input(page, country, COUNTRY_CODE)
    original = getattr(page, "_original", None)
    key_press = original.keyboard_press if original is not None else page.keyboard.press
    key_press("Tab")
    page.wait_for_timeout(250)
    if country.input_value().strip() != COUNTRY_CODE:
        raise RuntimeError(f"区号没有保持为 {COUNTRY_CODE}，停止发送")
    if report is not None:
        report["country_selection"] = {"selected": True, "reason": "input_edited",
                                       "value": COUNTRY_CODE}
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
    # Newer layouts put both headings in a short tab row while the QR is
    # its sibling. Walk up to the visible content panel before scanning.
    for _ in range(10):
        box = panel.bounding_box()
        if box and box["height"] >= 200:
            break
        parent = panel.locator("xpath=..")
        if not parent.count():
            break
        panel = parent
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
            # Use viewport coordinates, like the full-page evidence, instead
            # of locator content quads which may differ in CloakBrowser.
            png = page.screenshot(clip=box, timeout=5000)
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
        # Check the business result as well as the outer envelope. An outer
        # success must not hide an inner failure (or the other way around).
        codes = []
        messages = []
        for source in (data, payload):
            for key in ("error_code", "status_code", "code"):
                value = source.get(key)
                if type(value) is int:
                    codes.append(value)
                elif isinstance(value, str) and re.fullmatch(r"-?\d{1,12}", value):
                    codes.append(int(value))
            for key in ("description", "message", "error_msg", "errmsg", "status_msg"):
                value = source.get(key)
                if isinstance(value, str) and value and value not in messages:
                    messages.append(value)
        if codes:
            summary["code"] = next((code for code in codes if code != 0), codes[0])
        summary["message"] = " | ".join(messages)[:300]
        feedback = " | ".join(messages)
        if response.status == 429 or re.search(r"频繁|频率|次数.{0,8}(限制|上限)|too many|rate.?limit|frequen", feedback, re.I):
            summary.update(status="failed", reason="rate_limited")
        elif any(source.get("verify_center_decision_conf") for source in (data, payload)) or re.search(
                r"安全验证|完成验证|滑块|captcha|verification|verify", feedback, re.I):
            summary["status"] = "verification_required"
        elif response.status >= 400:
            summary["status"] = "failed"
        elif re.search(r"发送失败|请求失败|手机号.{0,8}(错误|不正确|无效)|fail|invalid|error", feedback, re.I):
            summary["status"] = "failed"
        elif "code" in summary and summary["code"] != 0:
            summary["status"] = "failed"
        elif summary.get("code") == 0 and 200 <= response.status < 300:
            summary["status"] = "request_accepted"
    except Exception as exc:
        summary["read_error"] = type(exc).__name__
        if response.status >= 400:
            summary["status"] = "failed"
        if response.status == 429:
            summary.update(status="failed", reason="rate_limited")
    return summary


def observe_sms_requests(page, report, recorder=None):
    """Read bodies after requestfinished; keep aborted requests distinct from replies."""
    pending = {}
    report["sms_requests"] = []

    def tracked(request):
        return report["send_attempted"] and request.method == "POST" and sms_endpoint(request.url)

    def on_request(request):
        if tracked(request):
            endpoint = urlsplit(request.url)
            item = {"endpoint": endpoint.scheme + "://" + endpoint.netloc + endpoint.path,
                    "state": "pending"}
            report["sms_requests"].append(item)
            pending[request] = item

    def on_finished(request):
        if request not in pending:
            return
        item = pending.pop(request)
        try:
            response = request.response()
            if response is None:
                item["state"] = "no_response"
                return
            report["sms_responses"].append(summarize_sms_response(response))
            item["state"] = "completed"
        except Exception as exc:
            item.update(state="read_error", error_type=type(exc).__name__)

    def on_failed(request):
        if request in pending:
            pending.pop(request)["state"] = "blocked" if recorder is not None else "network_error"

    # Context events also cover requests initiated by embedded frames.
    page.context.on("request", on_request)
    page.context.on("requestfinished", on_finished)
    page.context.on("requestfailed", on_failed)
    return pending


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
        page = browser.new_page(viewport={"width": 1440, "height": 1000},
                                service_workers="block")
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
        country = edit_country_code(page, report)
        report["country_code"] = COUNTRY_CODE
        type_input(page, field, phone)
        if country.input_value().strip() != COUNTRY_CODE:
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
            pending_sms = observe_sms_requests(page, report, recorder)
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
                report["ui_status"] = status
                for result in report["sms_responses"]:
                    if result["status"] in {"failed", "verification_required"}:
                        status = result["status"]
                        break
                    if result["status"] == "request_accepted" and status not in {"failed", "verification_required"}:
                        status = result["status"]
                report.update(status=status, feedback_text=text, button_text=button_text)
                # UI feedback may arrive before the HTTP body. Wait for the
                # in-flight response, within the existing timeout, without clicking again.
                if status in {"sent", "failed", "verification_required", "request_accepted"} and not pending_sms and time.monotonic() - clicked_at >= 2:
                    break
                page.wait_for_timeout(250)
            report["sms_response_state"] = (
                "completed" if report["sms_responses"] else
                "pending_timeout" if pending_sms else
                report["sms_requests"][-1]["state"] if report["sms_requests"] else "not_observed")
            if pending_sms and report["status"] in {"sent", "request_accepted"}:
                report["status"] = "unknown"
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
