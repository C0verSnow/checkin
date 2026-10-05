"""Shared Linux browser setup and rendered HTML capture."""

import argparse
import importlib
import math
from pathlib import Path
import subprocess
import sys


def ensure_cloakbrowser():
    """Use the current interpreter's pip only when cloakbrowser is absent."""
    try:
        return importlib.import_module("cloakbrowser")
    except ModuleNotFoundError as exc:
        if exc.name != "cloakbrowser":
            raise
    subprocess.run([sys.executable, "-m", "pip", "install", "cloakbrowser"], check=True)
    return importlib.import_module("cloakbrowser")


def nonnegative_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError("秒数必须是大于等于 0 的有限数字")
    return seconds


def positive_seconds(value):
    seconds = nonnegative_seconds(value)
    if seconds == 0:
        raise argparse.ArgumentTypeError("超时秒数必须大于 0")
    return seconds


def save_html(launch, url, output, timeout_seconds=60, wait_seconds=15):
    """Save the current DOM, including JavaScript changes, and close Chromium."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    browser = launch(headless=True, locale="zh-CN", timezone="Asia/Shanghai")
    try:
        page = browser.new_page()
        responses = {}
        page.on('response', lambda response: responses.__setitem__(response.url, response))
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
        # Video sites keep background connections open; avoid networkidle.
        page.wait_for_timeout(wait_seconds * 1000)
        from offline_page import snapshot
        html, report = snapshot(page, timeout_seconds, responses)
        if not html.strip():
            raise RuntimeError("浏览器返回了空页面")
        output.write_text(html, encoding="utf-8")
        import json
        output.with_suffix('.resources.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if report['failed_resources']:
            print(f"注意：{len(report['failed_resources'])} 个资源未能保存，详情见资源报告")
        print(f"已保存：{output.resolve()}（{output.stat().st_size} 字节）")
        print(f"当前页面：{page.url}")
        if response is None:
            raise RuntimeError("导航没有返回 HTTP 响应；已保存当前页面供排查")
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}；已保存当前页面供排查")
    finally:
        browser.close()


def main(url, default_output, argv=None):
    parser = argparse.ArgumentParser(description="在 Linux 上用 CloakBrowser 保存可离线打开的网页 HTML")
    parser.add_argument("--output", type=Path, default=Path(default_output))
    parser.add_argument("--timeout-seconds", type=positive_seconds, default=60)
    parser.add_argument("--wait-seconds", type=nonnegative_seconds, default=15)
    args = parser.parse_args(argv)
    if sys.platform != "linux":
        parser.error("请在 Linux 系统中运行，并使用 Python 虚拟环境")
    try:
        for module, package in [('bs4', 'beautifulsoup4'), ('tinycss2', 'tinycss2'), ('html5lib', 'html5lib')]:
            try:
                importlib.import_module(module)
            except ModuleNotFoundError as exc:
                if exc.name != module:
                    raise
                subprocess.run([sys.executable, '-m', 'pip', 'install', package], check=True)
        cloakbrowser = ensure_cloakbrowser()
        save_html(cloakbrowser.launch, url, args.output, args.timeout_seconds, args.wait_seconds)
    except Exception as exc:
        print(f"保存失败：{exc}", file=sys.stderr)
        return 1
    return 0
