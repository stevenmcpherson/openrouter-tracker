#!/usr/bin/env python3
"""OpenRouter Tracker — macOS menu bar app.

Shows account-wide credit balance in the menu bar.
Dropdown shows per-key usage vs. limit in a monospace table format,
auto-discovered via a provisioning key.

Requires: pip install rumps
Run: python3 tracker.py
"""

import datetime
import sys
import time

import rumps

import api_client
import config as cfg
import storage

APP_NAME = "OR Tracker"

# Status emoji (double-width in monospace)
GREEN = "\U0001F7E2"   # 🟢
YELLOW = "\U0001F7E1"   # 🟡
RED = "\U0001F534"      # 🔴
GRAY = "\U0001F7E3"     # 🟣

# Column widths for the table
NAME_W = 20
COL_W = 9   # for remaining, limit, daily, all-time columns

# ─── Monospace attributed titles via PyObjC ──────────────────────

try:
    from AppKit import NSFont, NSFontAttributeName
    from Foundation import NSAttributedString, NSMutableDictionary
    _HAS_FONTS = True
except ImportError:
    _HAS_FONTS = False

_mono_font = None


def _get_mono_font():
    global _mono_font
    if _mono_font is None:
        # 13pt matches the default macOS menu font size
        _mono_font = NSFont.monospacedSystemFontOfSize_weight_(13.0, 0.0)
    return _mono_font


def _set_mono_title(item, text):
    """Set an attributed title with monospace font on a rumps MenuItem."""
    if not _HAS_FONTS:
        item.title = text
        return
    font = _get_mono_font()
    attrs = NSMutableDictionary.dictionary()
    attrs.setObject_forKey_(font, NSFontAttributeName)
    attr_str = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
    item._menuitem.setAttributedTitle_(attr_str)


def _money(val, width=COL_W):
    """Format a dollar amount right-aligned to width."""
    return f"${val:.2f}".rjust(width)


# ─── App ─────────────────────────────────────────────────────────

class ORTrackerApp(rumps.App):
    def __init__(self):
        super(ORTrackerApp, self).__init__(name=APP_NAME, title="OR...", quit_button=None)
        self.cfg = cfg.load_config()
        self.last_refresh = 0

        storage.init_db()

        interval = self.cfg.get("poll_interval_seconds", 300)
        self.timer = rumps.Timer(self._tick, interval)
        self.timer.start()

        rumps.Timer(self._initial_fetch, 1).start()

    # ─── Timer / refresh ────────────────────────────────────────────

    def _initial_fetch(self, _sender):
        self._fetch_and_update()

    def _tick(self, _sender):
        self._fetch_and_update()

    def _force_refresh(self, _sender):
        self.title = "OR..."
        self._fetch_and_update()

    # ─── API calls ──────────────────────────────────────────────────

    def _fetch_and_update(self):
        prov = self.cfg.get("provisioning_key", "")

        if not prov:
            self.title = "OR \u26a0\ufe0f"
            self._rebuild_menu(error="No provisioning key in config.json")
            return

        try:
            credits = api_client.get_credits(prov)
        except Exception as e:
            self.title = "OR \u26a0\ufe0f"
            self._rebuild_menu(error=str(e))
            return

        try:
            keys = api_client.list_keys(prov)
        except Exception as e:
            self.title = "OR \u26a0\ufe0f"
            self._rebuild_menu(credits=credits, error=f"Keys: {e}")
            return

        for k in keys:
            name = k.get("name") or k.get("label", "unnamed")
            storage.save_snapshot(
                label=name,
                key_suffix=k.get("label", ""),
                credits=credits,
                key_info=k,
                status="disabled" if k.get("disabled") else "ok",
            )

        remaining = credits["remaining"]
        threshold = self.cfg.get("low_credit_threshold", 10.0)
        if remaining <= threshold:
            self.title = f"OR \U0001F534${remaining:.2f}"
        elif remaining <= threshold * 3:
            self.title = f"OR \U0001F7E1${remaining:.2f}"
        else:
            self.title = f"OR ${remaining:.2f}"

        self._rebuild_menu(credits=credits, keys=keys)
        self.last_refresh = time.time()

    # ─── Menu builder ───────────────────────────────────────────────

    def _rebuild_menu(self, credits=None, keys=None, error=None):
        self.menu.clear()

        if error and not keys:
            item = rumps.MenuItem(f"\u26a0\ufe0f  {error[:60]}")
            self.menu.add(item)
            self.menu.add(None)
            now = datetime.datetime.now().strftime("%H:%M:%S")
            self.menu.add(rumps.MenuItem(f"Last attempt {now}"))
            self.menu.add(None)
            self._add_settings()
            return

        # ── KEYS FIRST (top of menu) ──
        if keys:
            active = [k for k in keys if not k.get("disabled")]
            disabled = [k for k in keys if k.get("disabled")]

            # Table header (disabled, monospace)
            header_text = (
                f"   {'Key':<{NAME_W}s}"
                f"  {'Daily':>{COL_W}s}"
                f"  {'Rem':>{COL_W}s}"
                f"  {'Limit':>{COL_W}s}"
                f"  {'All-time':>{COL_W}s}"
            )
            header = rumps.MenuItem(header_text)
            header.enabled = False
            _set_mono_title(header, header_text)
            self.menu.add(header)
            self.menu.add(None)

            for k in active:
                self.menu.add(self._build_key_item(k))

            if disabled:
                self.menu.add(None)
                for k in disabled:
                    self.menu.add(self._build_key_item(k))

        self.menu.add(None)

        # ── ACCOUNT BALANCE ──
        if credits:
            remaining = credits["remaining"]
            total = credits["total_credits"]
            used = credits["total_usage"]
            pct = (used / total * 100) if total > 0 else 0

            if remaining <= self.cfg.get("low_credit_threshold", 10.0):
                bal_icon = "\U0001F534"
            elif remaining <= self.cfg.get("low_credit_threshold", 10.0) * 3:
                bal_icon = "\U0001F7E1"
            else:
                bal_icon = "\u2705"

            bar = _progress_bar(pct, 12)
            bal_item = rumps.MenuItem(f"{bal_icon}  Balance  ${remaining:.2f} / ${total:.2f}")
            bal_item.subtitle = f"{bar}  {pct:.0f}% used"
            self.menu.add(bal_item)
            # Also add a separate disabled item with just the bar (in case subtitles don't render)
            bar_item = rumps.MenuItem(f"   {bar}  {pct:.0f}% used of ${total:.2f}")
            bar_item.enabled = False
            self.menu.add(bar_item)

        elif error:
            err_item = rumps.MenuItem(f"\u26a0\ufe0f  {error[:60]}")
            self.menu.add(err_item)

        self.menu.add(None)

        # ── Footer ──
        now = datetime.datetime.now().strftime("%H:%M:%S")
        updated_item = rumps.MenuItem(f"\U0001F552  Updated {now}")
        updated_item.enabled = False
        self.menu.add(updated_item)

        self.menu.add(None)
        self._add_settings()

    def _build_key_item(self, k):
        """Build a single key menu item as a monospace table row."""
        name = k.get("name") or "unnamed"
        limit = k.get("limit", 0)
        remaining = k.get("limit_remaining", 0)
        usage = k.get("usage", 0)
        daily = k.get("usage_daily", 0)
        monthly = k.get("usage_monthly", 0)
        disabled = k.get("disabled", False)

        name_col = name[:NAME_W].ljust(NAME_W)

        if disabled:
            line = (
                f"{GRAY}  {name_col}"
                f"  {'—':>{COL_W}s}"
                f"  {'disabled':>{COL_W}s}"
                f"  {'—':>{COL_W}s}"
                f"  {_money(usage)}"
            )
            item = rumps.MenuItem(line)
            _set_mono_title(item, line)
            return item

        if limit and limit > 0:
            # Use monthly usage (not all-time) for percentage — the limit is monthly
            pct_used = (monthly / limit * 100) if limit > 0 else 0
            if pct_used >= 80:
                dot = RED
            elif pct_used >= 50:
                dot = YELLOW
            else:
                dot = GREEN

            line = (
                f"{dot}  {name_col}"
                f"  {_money(daily)}"
                f"  {_money(remaining)}"
                f"  {_money(limit)}"
                f"  {_money(usage)}"
            )
            bar = _progress_bar(pct_used, 12)
            sub = f"{bar}  {pct_used:.1f}% of monthly limit  \u00b7  this month: ${monthly:.2f}"
        else:
            dot = GRAY
            line = (
                f"{dot}  {name_col}"
                f"  {_money(daily)}"
                f"  {'no limit':>{COL_W}s}"
                f"  {'—':>{COL_W}s}"
                f"  {_money(usage)}"
            )
            sub = f"this month: ${monthly:.2f}  \u00b7  all-time: ${usage:.2f}"

        item = rumps.MenuItem(line)
        item.subtitle = sub
        _set_mono_title(item, line)
        return item

    def _add_settings(self):
        settings = rumps.MenuItem("\u2699\ufe0f  Settings")
        settings.add(rumps.MenuItem("Refresh Now", callback=self._force_refresh))
        settings.add(None)
        settings.add(rumps.MenuItem("Quit", callback=self._quit))
        self.menu.add(settings)

    # ─── Actions ────────────────────────────────────────────────────

    def _quit(self, _sender):
        rumps.quit_application()


def _progress_bar(pct, width=12):
    pct = max(0, min(pct, 100))
    filled = int(pct / 100 * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


if __name__ == "__main__":
    try:
        import rumps
    except ImportError:
        print("rumps is not installed. Install with: pip install rumps")
        print("Then run: python3 tracker.py")
        sys.exit(1)

    ORTrackerApp().run()
