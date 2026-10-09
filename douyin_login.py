"""Capture Douyin's login QR and the result of one SMS request with CloakBrowser."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

from capture_page import ensure_cloakbrowser, positive_seconds

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


def select_china_country(page, field):
    """The overseas runner defaults to +1; never send until +86 is selected."""
    country_pattern = re.compile(r"^\+\s*\d{1,4}$")

    def country_in(row):
        label = visible(row.get_by_text(country_pattern, exact=True))
        if label is not None:
            return label, re.sub(r"\s", "", label.inner_text()).lstrip("+")
        # Douyin can render the country code as a read-only input value.
        inputs = row.locator("input")
        for index in range(inputs.count()):
            candidate = inputs.nth(index)
            if candidate.is_visible() and re.fullmatch(r"\+?\d{1,4}", candidate.input_value()):
                return candidate, candidate.input_value().lstrip("+")
        return None, None

    row = field
    country, code = None, None
    for _ in range(5):
        row = row.locator("xpath=..")
        country, code = country_in(row)
        if country is not None:
            break
    if country is None:
        raise RuntimeError("没有找到手机号区号，不能确认收件号码")
    if code != "86":
        country.click()
        option = page.get_by_text(re.compile(r"^\+?\s*86$"), exact=True)
        option.first.wait_for()
        choice = visible(option)
        if choice is None:
            raise RuntimeError("没有找到中国大陆 +86 选项")
        choice.click()
    _, selected_code = country_in(row)
    if selected_code != "86":
        raise RuntimeError("中国大陆 +86 区号没有选中，停止发送")


def open_login(page):
    if phone_field(page) is not None or visible(page.get_by_text("扫码登录", exact=True)) is not None:
        return
    button = visible(page.get_by_role("button", name="登录", exact=True))
    if button is None:
        button = visible(page.get_by_text("登录", exact=True))
    if button is None:
        raise RuntimeError("没有找到登录入口")
    button.click()
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


def capture_login(launch, phone, output, send_code=False, timeout_seconds=60, headed=False, url=URL):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Remove old evidence so a failed run cannot inherit a successful screenshot.
    for name in ("login.png", "login-qr.png", "before-send.png", "sms-result.png", "result.json"):
        (output / name).unlink(missing_ok=True)
    report = {"time_utc": datetime.now(timezone.utc).isoformat(), "phone": phone,
              "status": "not_requested", "send_clicked": False, "qr_saved": False}
    browser = None
    page = None
    try:
        browser = launch(headless=not headed, locale="zh-CN", timezone="Asia/Shanghai")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
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
        select_china_country(page, field)
        report["country_code"] = "+86"
        field.fill(phone)
        # Agree to the login terms only in the visible phone form when required.
        checkbox = visible(page.get_by_role("checkbox"))
        if checkbox is not None and not checkbox.is_checked():
            checkbox.check()
        send = visible(page.get_by_text(SEND_TEXT, exact=True))
        if send is None:
            raise RuntimeError("没有找到发送验证码按钮")
        page.screenshot(path=str(output / "before-send.png"), full_page=True)
        if send_code:
            # Exactly one click; do not retry SMS requests on ambiguous feedback.
            report["send_clicked"] = True
            send.click()
            report["status"] = "unknown"
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                text = page.locator("body").inner_text()
                feedback_button = visible(page.get_by_text(re.compile(r"\d+\s*(秒|s|S).{0,12}|重新发送|重新获取")))
                button_text = feedback_button.inner_text() if feedback_button is not None else ""
                status = sms_result(text, button_text)
                report.update(status=status, page_text=text, button_text=button_text)
                if status in {"sent", "failed", "verification_required"}:
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
    print(json.dumps({key: value for key, value in report.items() if key not in {"page_text", "form_controls"}}, ensure_ascii=False, indent=2))
    print(f"截图和报告：{args.output_dir.resolve()}")
    return 0 if report["qr_saved"] and report["status"] in {"sent", "not_requested"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
