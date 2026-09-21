"""State-changing feature actions driven by discovered profiles.

Every action consumes a Control discovered by core/control_discovery
(never ad-hoc selectors), performs the toggle, then re-reads state to
verify. Raises FeatureControlError when verification fails.
"""

from __future__ import annotations


class FeatureControlError(RuntimeError):
    pass


async def _click(page, selector: str, timeout: int = 8000) -> None:
    await page.click(selector, timeout=timeout)


async def _state_of(page, selector: str) -> dict:
    return await page.evaluate("""(sel) => {
      const e = document.querySelector(sel);
      if (!e) return {missing: true};
      return {pressed: e.getAttribute('aria-pressed'),
              checked: e.getAttribute('aria-checked'),
              expanded: e.getAttribute('aria-expanded'),
              state: e.getAttribute('data-state')};
    }""", selector)


def _is_on(state: dict) -> bool | None:
    for key in ("pressed", "checked"):
        v = state.get(key)
        if v is not None:
            return str(v).lower() == "true"
    return None


async def set_toggle(page, control: dict, on: bool) -> dict:
    """Set a toggle control (thinking/search) to on/off with verification."""
    selector = control["selector"]
    before = await _state_of(page, selector)
    if before.get("missing"):
        raise FeatureControlError(f"control not found: {selector}")
    current = _is_on(before)
    if current is on:
        return {"selector": selector, "already": True, "state": before}
    await _click(page, selector)
    await page.wait_for_timeout(800)
    after = await _state_of(page, selector)
    verified = _is_on(after)
    if verified is not None and verified is not on:
        raise FeatureControlError(f"toggle did not change state: {selector} -> {after}")
    return {"selector": selector, "already": False, "before": before, "after": after}
