"""Freeze a rendered DOM and embed its display resources in one portable HTML."""

import base64
import json
import mimetypes
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup
import tinycss2


# Work on a clone: removing the site's scripts must not disturb resource loading.
SNAPSHOT = r"""() => {
    const root = document.documentElement.cloneNode(true);
    const originals = [...document.querySelectorAll('*')];
    const copies = [...root.querySelectorAll('*')];
    originals.shift(); // querySelectorAll includes documentElement, the clone does not
    originals.forEach((el, i) => {
        const copy = copies[i];
        if (!copy) return;
        if (el.tagName === 'IMG') {
            copy.setAttribute('src', el.currentSrc || el.src);
            copy.removeAttribute('srcset'); copy.removeAttribute('loading');
        }
        if (el.tagName === 'INPUT') {
            copy.setAttribute('value', el.value);
            if (el.checked) copy.setAttribute('checked', '');
            else copy.removeAttribute('checked');
        }
        if (el.tagName === 'TEXTAREA') copy.textContent = el.value;
        if (el.tagName === 'OPTION') {
            if (el.selected) copy.setAttribute('selected', '');
            else copy.removeAttribute('selected');
        }
        if (el.tagName === 'CANVAS') {
            try { const img = document.createElement('img');
                img.src = el.toDataURL(); img.style.cssText = el.style.cssText;
                img.width = el.width; img.height = el.height; copy.replaceWith(img);
            } catch (_) { /* tainted canvases cannot be exported */ }
        }
        if (el.tagName === 'STYLE' && el.sheet) {
            try { copy.textContent = [...el.sheet.cssRules].map(r => r.cssText).join('\n'); }
            catch (_) {}
        }
    });
    for (const sheet of document.adoptedStyleSheets || []) {
        const style = document.createElement('style');
        style.textContent = [...sheet.cssRules].map(r => r.cssText).join('\n');
        root.querySelector('head').appendChild(style);
    }
    const cssURLs = new Set();
    for (const el of document.querySelectorAll('*')) {
        const rect = el.getBoundingClientRect();
        if (!rect.width || !rect.height || getComputedStyle(el).visibility === 'hidden') continue;
        for (const pseudo of [null, '::before', '::after']) {
            const style = getComputedStyle(el, pseudo);
            for (const property of style) {
                for (const match of style.getPropertyValue(property).matchAll(/url\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*))\s*\)/g)) {
                    cssURLs.add(new URL(match[1] ?? match[2] ?? match[3].trim(), document.baseURI).href);
                }
            }
        }
    }
    return {html: '<!DOCTYPE html>\n' + root.outerHTML, base: document.baseURI, css_urls: [...cssURLs]};
}"""


class Resources:
    def __init__(self, page, timeout_seconds, responses=None, css_urls=None):
        self.page = page
        self.timeout = timeout_seconds * 1000
        self.cache = {}
        self.failures = {}
        self.active = set()
        self.responses = responses or {}
        self.css_urls = None if css_urls is None else set(css_urls)
        self.unused_failures = {}

    def fetch(self, url):
        cached = self.responses.get(url)
        if cached is not None:
            try:
                if cached.ok:
                    return cached.body(), cached.headers.get('content-type', '').split(';')[0], cached.url
            except Exception:
                pass  # The browser may have evicted a response; request it with its cookies.
        response = self.page.request.get(url, headers={"Referer": self.page.url}, timeout=self.timeout)
        try:
            if not response.ok:
                raise RuntimeError(f"HTTP {response.status}")
            return response.body(), response.headers.get("content-type", "").split(";")[0], response.url
        finally:
            response.dispose()

    def embed(self, value, base, css=False, optional=False):
        value = value.strip()
        if not value or value.startswith(('#', 'data:')):
            return value
        url, fragment = urldefrag(urljoin(base, value))
        if urlsplit(url).scheme not in ('http', 'https', 'blob'):
            self.failures[url] = '不支持的资源地址'
            return ''
        key = (url, css)
        if key in self.cache:
            if not optional and url in self.unused_failures:
                self.failures[url] = self.unused_failures.pop(url)
            return self.cache[key] + ('#' + fragment if fragment else '')
        if key in self.active:
            self.failures[url] = '循环引用'
            return ''
        self.active.add(key)
        try:
            if url.startswith('blob:'):
                result = self.page.evaluate("""async url => {
                    const r = await fetch(url); const b = await r.blob();
                    return await new Promise(resolve => {const f = new FileReader();
                        f.onload = () => resolve(f.result); f.readAsDataURL(b);});
                }""", url)
            else:
                body, mime, final_url = self.fetch(url)
                mime = mime or mimetypes.guess_type(urlsplit(url).path)[0] or 'application/octet-stream'
                if css or mime == 'text/css':
                    rules, _ = tinycss2.parse_stylesheet_bytes(body)
                    self.rewrite_tokens(rules, final_url)
                    body = tinycss2.serialize(rules).encode('utf-8')
                    mime = 'text/css;charset=utf-8'
                result = f'data:{mime};base64,' + base64.b64encode(body).decode('ascii')
            self.cache[key] = result
            return result + ('#' + fragment if fragment else '')
        except Exception as exc:
            (self.unused_failures if optional else self.failures)[url] = str(exc)
            self.cache[key] = ''
            return ''
        finally:
            self.active.remove(key)

    def css_resource(self, value, base):
        url = urljoin(base, value)
        mime = mimetypes.guess_type(urlsplit(url).path)[0] or ''
        # Sites ship CSS for hidden dialogs and other pages too. A failed image
        # unused by every visible element/pseudo-element is reported separately.
        optional = self.css_urls is not None and url not in self.css_urls and mime.startswith('image/')
        return self.embed(value, base, optional=optional)

    def rewrite_tokens(self, tokens, base):
        for token in tokens:
            if token.type == 'url':
                value = self.css_resource(token.value, base)
                token.value = value
                token.representation = 'url(' + json.dumps(value) + ')'
            elif token.type == 'function' and token.lower_name == 'url':
                args = [t for t in token.arguments if t.type not in ('whitespace', 'comment')]
                if len(args) == 1 and args[0].type == 'string':
                    value = self.css_resource(args[0].value, base)
                    token.arguments = tinycss2.parse_component_value_list(json.dumps(value))
            elif token.type == 'function' and token.lower_name in ('image-set', '-webkit-image-set'):
                for item in token.arguments:
                    if item.type == 'string':
                        value = self.css_resource(item.value, base)
                        item.value = value
                        item.representation = json.dumps(value)
                self.rewrite_tokens(token.arguments, base)
            elif token.type == 'at-rule' and token.lower_at_keyword == 'import':
                for item in token.prelude:
                    if item.type in ('string', 'url'):
                        value = self.embed(item.value, base, css=True)
                        item.value = value
                        item.representation = json.dumps(value) if item.type == 'string' else 'url(' + json.dumps(value) + ')'
                        break
                    if item.type == 'function' and item.lower_name == 'url':
                        args = [t for t in item.arguments if t.type == 'string']
                        if args:
                            value = self.embed(args[0].value, base, css=True)
                            item.arguments = tinycss2.parse_component_value_list(json.dumps(value))
                        break
            else:
                for attr in ('prelude', 'content', 'arguments'):
                    nested = getattr(token, attr, None)
                    if nested is not None:
                        self.rewrite_tokens(nested, base)

    def css(self, text, base):
        tokens = tinycss2.parse_component_value_list(text)
        self.rewrite_tokens(tokens, base)
        return tinycss2.serialize(tokens)


def snapshot(page, timeout_seconds=30, responses=None):
    document = page.evaluate(SNAPSHOT)
    if not document['html'].strip():
        raise RuntimeError('浏览器返回了空页面')
    soup = BeautifulSoup(document['html'], 'html5lib')
    base = document['base']
    resources = Resources(page, timeout_seconds, responses, document.get('css_urls'))
    for tag in soup.find_all(['script', 'base', 'iframe', 'object', 'embed']):
        tag.decompose()
    for tag in soup.find_all('meta'):
        if tag.get('http-equiv') or tag.get('charset'):
            tag.decompose()
    charset = soup.new_tag('meta', charset='utf-8')
    soup.head.insert(0, charset)
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith('on') or attr in ('integrity', 'crossorigin', 'nonce'):
                del tag[attr]
        if tag.name == 'link':
            if 'stylesheet' in tag.get('rel', []):
                tag['href'] = resources.embed(tag.get('href', ''), base, css=True)
            elif 'icon' in tag.get('rel', []):
                tag['href'] = resources.embed(tag.get('href', ''), base)
            else:
                tag.decompose()
                continue
        if tag.name == 'style':
            rules = tinycss2.parse_stylesheet(tag.string or tag.get_text())
            resources.rewrite_tokens(rules, base)
            tag.string = tinycss2.serialize(rules).replace('</style', r'<\/style')
        if tag.has_attr('style'):
            tag['style'] = resources.css(tag['style'], base)
        for attr in ('src', 'poster', 'background'):
            if tag.has_attr(attr):
                if tag.name in ('video', 'audio', 'source') and attr == 'src':
                    del tag[attr]  # Streaming video is accessed through the original website.
                else:
                    tag[attr] = resources.embed(tag[attr], base)
        if tag.name in ('image', 'use'):
            for attr in ('href', 'xlink:href'):
                if tag.has_attr(attr):
                    value = tag[attr]
                    if tag.name == 'use' and value and not value.startswith('#'):
                        # External SVG use references are blocked for file://; inline the symbol.
                        url, fragment = urldefrag(urljoin(base, value))
                        try:
                            body, _, _ = resources.fetch(url)
                            svg = BeautifulSoup(body, 'html5lib')
                            symbol = svg.find(id=fragment) if fragment else svg.find('svg')
                            if symbol is None:
                                raise RuntimeError('SVG 符号不存在')
                            symbol.name = 'svg'
                            symbol.attrs.pop('id', None)
                            for key, value in tag.attrs.items():
                                if key not in ('href', 'xlink:href'):
                                    symbol[key] = value
                            tag.replace_with(symbol)
                        except Exception as exc:
                            resources.failures[url] = str(exc)
                        break
                    tag[attr] = resources.embed(value, base)
        if tag.name == 'a' and tag.has_attr('href'):
            href = tag['href']
            tag['href'] = '' if href.lower().startswith('javascript:') else urljoin(base, href) if not href.startswith('#') else href
        if tag.name == 'form':
            tag['action'] = urljoin(base, tag.get('action', page.url))
        for attr in ('srcset', 'autoplay'):
            tag.attrs.pop(attr, None)
    # Sanitize imported SVG as well as the original DOM.
    for tag in soup.find_all('script'):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith('on'):
                del tag[attr]
    return str(soup), {
        'page': page.url,
        'embedded_resources': sum(bool(value) for value in resources.cache.values()),
        'failed_resources': resources.failures,
        'unavailable_unused_images': resources.unused_failures,
    }
