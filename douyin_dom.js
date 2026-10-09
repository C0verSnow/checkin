// Browser-side helper used by douyin_login.py. No HTTP requests or SMS clicks.
({
  focusInput(el) {
    el.focus();
    return document.activeElement === el;
  }
})
