"""Save Douyin's 罗生门 search page; shared setup installs cloakbrowser via pip."""

from capture_page import main

URL = "https://www.douyin.com/search/%E7%BD%97%E7%94%9F%E9%97%A8"

if __name__ == "__main__":
    raise SystemExit(main(URL, "output/douyin.html"))
