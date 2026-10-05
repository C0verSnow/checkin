"""Remote CI: reopen an actual site capture offline and record display diagnostics."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_page import ensure_cloakbrowser


def verify(output):
    output = Path(output).resolve()
    browser = ensure_cloakbrowser().launch(headless=True)
    try:
        context = browser.new_context(offline=True, locale='zh-CN')
        page = context.new_page()
        requests = []
        page.on('request', lambda request: requests.append(request.url))
        page.goto(output.as_uri(), wait_until='load')
        page.wait_for_timeout(1000)
        diagnostics = page.evaluate('''() => ({
            text_length: document.body.innerText.trim().length,
            images: document.images.length,
            broken_visible_images: [...document.images].filter(img => {
                const rect = img.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && (!img.complete || !img.naturalWidth);
            }).length,
            online_links: [...document.querySelectorAll('a[href]')].filter(a => /^https?:/.test(a.href)).length
        })''')
        diagnostics['external_requests'] = [url for url in requests if url.startswith(('http:', 'https:'))]
        report = json.loads(output.with_suffix('.resources.json').read_text(encoding='utf-8'))
        diagnostics['failed_resources'] = len(report['failed_resources'])
        diagnostics['unavailable_unused_images'] = len(report.get('unavailable_unused_images', {}))
        page.screenshot(path=str(output.with_suffix('.png')), full_page=True)
        output.with_suffix('.verification.json').write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(diagnostics, ensure_ascii=False))
        if not diagnostics['text_length'] or diagnostics['external_requests']:
            raise RuntimeError('离线页面为空或仍在请求外部资源')
        if diagnostics['broken_visible_images'] or diagnostics['failed_resources']:
            raise RuntimeError('存在没有保存成功的显示资源，查看资源报告和截图')
    finally:
        browser.close()


if __name__ == '__main__':
    verify(sys.argv[1])
