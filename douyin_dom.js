// Browser-side helpers used by douyin_login.py. No HTTP requests or SMS clicks.
({
  focusInput(el) {
    el.focus();
    return document.activeElement === el;
  },
  selectChina(input) {
    const listId = input.getAttribute('aria-controls') || input.getAttribute('aria-owns');
    const list = listId ? document.getElementById(listId) : null;
    if (!list) return {selected: false, reason: 'country_list_missing'};
    // Match the whole option, not a text span or an offscreen duplicate.
    const rows = [...list.querySelectorAll('[role="option"], li, [id^="areacode_item_"]')];
    const row = rows.find(el => {
      const text = (el.innerText || '').replace(/\s+/g, ' ').trim();
      const rect = el.getBoundingClientRect();
      return /^中国\s*\+86$/.test(text) && rect.width > 0 && rect.height > 0;
    });
    if (!row) return {selected: false, reason: 'china_option_missing'};
    row.scrollIntoView({block: 'nearest'});
    const rect = row.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
    const unobscured = hit === row || row.contains(hit);
    if (unobscured) row.click();
    return {selected: unobscured, reason: unobscured ? 'option_clicked' : 'option_obscured',
      option_id: row.id, option_text: (row.innerText || '').trim()};
  }
})
