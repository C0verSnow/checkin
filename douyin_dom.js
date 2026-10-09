// Browser-side helper used by douyin_login.py. No HTTP requests or SMS clicks.
({
  setInputValue(el, value) {
    el.focus();
    if (document.activeElement !== el) return false;
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype, "value").set;
    setter.call(el, value);
    // Notify controlled inputs through their ordinary input/change listeners.
    el.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: value}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
    return el.value === value;
  },
  focusInput(el) {
    el.focus();
    return document.activeElement === el;
  }
})
