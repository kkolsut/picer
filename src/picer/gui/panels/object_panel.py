"""Object panel: DSO catalog selector, find entry, info display, live HA ticker."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable, Optional
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from picer.objects import catalog as cat_module
from picer.objects import store
from picer.objects.models import DeepSkyObject

if TYPE_CHECKING:
    from picer.core.api_client import APIClient


# ── Geocoding ─────────────────────────────────────────────────────────────────

def _geocode(query: str) -> list[dict]:
    """Call Nominatim, return list of {display_name, lat, lon} (up to 5)."""
    import urllib.request
    import urllib.parse
    import json as _json
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 5})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "picer-astronomy-app/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return _json.loads(resp.read())


# ── Coordinate helpers ────────────────────────────────────────────────────────

def _compute_ha(ra_deg: float, lon: float) -> float:
    """Return hour angle in hours, normalised to (−12, +12]."""
    from astropy.time import Time
    import astropy.units as u
    now = Time.now()
    lst = now.sidereal_time("apparent", longitude=lon * u.deg)
    ha = lst.hour - ra_deg / 15.0
    while ha > 12:
        ha -= 24
    while ha <= -12:
        ha += 24
    return ha


def _compute_alt(ha_hours: float, dec_deg: float, lat_deg: float) -> float:
    """Return altitude above horizon in degrees (−90 … +90)."""
    import math
    ha_rad = math.radians(ha_hours * 15.0)
    dec_rad = math.radians(dec_deg)
    lat_rad = math.radians(lat_deg)
    sin_alt = (math.sin(dec_rad) * math.sin(lat_rad)
               + math.cos(dec_rad) * math.cos(lat_rad) * math.cos(ha_rad))
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))


def _compute_airmass(alt_deg: float) -> Optional[float]:
    """Kasten & Young (1989) airmass. Returns None when object is below horizon."""
    if alt_deg <= 0:
        return None
    import math
    return 1.0 / (math.sin(math.radians(alt_deg))
                  + 0.50572 * (alt_deg + 6.07995) ** -1.6364)


def _fmt_ha(ha: float) -> str:
    sign = "+" if ha >= 0 else "−"
    ha_abs = abs(ha)
    h = int(ha_abs)
    m = int((ha_abs - h) * 60)
    s = int(((ha_abs - h) * 60 - m) * 60)
    return f"{sign}{h:02d}h {m:02d}m {s:02d}s"


def _fmt_ra(ra_deg: float) -> str:
    total_s = ra_deg * 3600.0 / 15.0
    h = int(total_s // 3600)
    m = int((total_s % 3600) // 60)
    s = total_s % 60
    return f"{h:02d}h {m:02d}m {s:05.2f}s"


def _fmt_dec(dec_deg: float) -> str:
    sign = "+" if dec_deg >= 0 else "−"
    dec_abs = abs(dec_deg)
    d = int(dec_abs)
    m = int((dec_abs - d) * 60)
    s = int(((dec_abs - d) * 60 - m) * 60)
    return f"{sign}{d:02d}° {m:02d}′ {s:02d}″"


# ── Save-location dialog ──────────────────────────────────────────────────────

class _SaveLocationDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window, prefill: str,
                 on_saved: "Callable[[str], None]") -> None:
        super().__init__()
        self.set_title("Save Location")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        self.set_child(box)

        self._entry = Gtk.Entry()
        self._entry.set_placeholder_text("e.g. Home")
        self._entry.set_text(prefill)
        self._entry.set_hexpand(True)
        self._entry.connect("activate", lambda _: self._on_save())
        box.append(self._entry)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        btn_row.set_margin_top(4)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _: self.close())
        btn_row.append(cancel)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _: self._on_save())
        btn_row.append(save_btn)
        box.append(btn_row)

        self._on_saved = on_saved

    def _on_save(self) -> None:
        name = self._entry.get_text().strip()
        if not name:
            return
        self._on_saved(name)
        self.close()


# ── Panel ─────────────────────────────────────────────────────────────────────

class ObjectPanel(Gtk.Frame):
    def __init__(self, client: Optional["APIClient"] = None) -> None:
        super().__init__(label="Object")
        self._client = client
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        outer.set_margin_top(8)
        outer.set_margin_bottom(10)
        self.set_child(outer)

        # ── Catalog row ───────────────────────────────────────────────
        cat_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cat_lbl = Gtk.Label(label="Catalog:")
        cat_lbl.set_width_chars(8)
        cat_lbl.set_xalign(0)
        cat_row.append(cat_lbl)

        self._cat_combo = Gtk.ComboBoxText()
        self._cat_combo.set_hexpand(True)
        self._cat_combo.set_size_request(60, -1)
        self._cat_combo.get_cells()[0].set_property("ellipsize", Pango.EllipsizeMode.END)
        for key in cat_module.CATALOG_KEYS:
            self._cat_combo.append(key, cat_module.catalog_label(key))
        self._cat_combo.set_active_id("M")
        self._cat_combo.connect("changed", self._on_catalog_changed)
        cat_row.append(self._cat_combo)
        outer.append(cat_row)

        # ── Object search row ─────────────────────────────────────────
        obj_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        obj_lbl = Gtk.Label(label="Object:")
        obj_lbl.set_width_chars(8)
        obj_lbl.set_xalign(0)
        obj_row.append(obj_lbl)

        self._obj_entry = Gtk.Entry()
        self._obj_entry.set_hexpand(True)
        self._obj_entry.set_size_request(40, -1)
        self._obj_entry.set_placeholder_text("Number or name…")
        self._obj_entry.connect("changed", self._on_entry_changed)
        self._obj_entry.connect("activate", lambda _: self._on_find())
        obj_row.append(self._obj_entry)

        find_btn = Gtk.Button(label="Find")
        find_btn.connect("clicked", lambda _: self._on_find())
        obj_row.append(find_btn)
        outer.append(obj_row)

        # ── Object info block ─────────────────────────────────────────
        self._info_name = Gtk.Label(label="")
        self._info_name.set_xalign(0)
        self._info_name.set_ellipsize(Pango.EllipsizeMode.END)
        outer.append(self._info_name)

        self._info_type = Gtk.Label(label="")
        self._info_type.set_xalign(0)
        self._info_type.set_ellipsize(Pango.EllipsizeMode.END)
        self._info_type.add_css_class("dim-label")
        outer.append(self._info_type)

        self._info_ra = Gtk.Label(label="")
        self._info_ra.set_xalign(0)
        outer.append(self._info_ra)

        self._info_dec = Gtk.Label(label="")
        self._info_dec.set_xalign(0)
        outer.append(self._info_dec)

        self._ha_label = Gtk.Label(label="")
        self._ha_label.set_xalign(0)
        self._ha_label.set_visible(False)
        outer.append(self._ha_label)

        self._alt_label = Gtk.Label(label="")
        self._alt_label.set_xalign(0)
        self._alt_label.set_visible(False)
        outer.append(self._alt_label)

        self._airmass_label = Gtk.Label(label="")
        self._airmass_label.set_xalign(0)
        self._airmass_label.set_visible(False)
        outer.append(self._airmass_label)

        # ── Separator ─────────────────────────────────────────────────
        outer.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ── Observer Location ─────────────────────────────────────────
        obs_lbl = Gtk.Label(label="Observer Location")
        obs_lbl.set_xalign(0)
        outer.append(obs_lbl)

        # City search row
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._city_entry = Gtk.Entry()
        self._city_entry.set_hexpand(True)
        self._city_entry.set_size_request(40, -1)
        self._city_entry.set_placeholder_text("City or country…")
        self._city_entry.connect("activate", lambda _: self._on_search())
        search_row.append(self._city_entry)

        self._search_btn = Gtk.Button(label="Search")
        self._search_btn.connect("clicked", lambda _: self._on_search())
        search_row.append(self._search_btn)
        outer.append(search_row)

        # Search status label
        self._search_status = Gtk.Label(label="")
        self._search_status.set_xalign(0)
        self._search_status.add_css_class("dim-label")
        self._search_status.set_ellipsize(Pango.EllipsizeMode.END)
        outer.append(self._search_status)

        # Results row (hidden until search returns)
        self._result_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._result_combo = Gtk.ComboBoxText()
        self._result_combo.set_hexpand(True)
        self._result_combo.set_size_request(40, -1)
        self._result_combo.get_cells()[0].set_property("ellipsize", Pango.EllipsizeMode.END)
        self._result_row.append(self._result_combo)

        use_result_btn = Gtk.Button(label="Use")
        use_result_btn.set_tooltip_text("Apply this location")
        use_result_btn.connect("clicked", lambda _: self._on_use_result())
        self._result_row.append(use_result_btn)
        self._result_row.set_visible(False)
        outer.append(self._result_row)

        # Manual lat/lon row
        loc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        lat_lbl = Gtk.Label(label="Lat:")
        lat_lbl.set_xalign(0)
        loc_row.append(lat_lbl)

        self._lat_entry = Gtk.Entry()
        self._lat_entry.set_placeholder_text("48.8566")
        self._lat_entry.set_size_request(70, -1)
        self._lat_entry.connect("changed", self._on_location_changed)
        loc_row.append(self._lat_entry)
        loc_row.append(Gtk.Label(label="°"))

        lon_lbl = Gtk.Label(label="Lon:")
        lon_lbl.set_xalign(0)
        lon_lbl.set_margin_start(6)
        loc_row.append(lon_lbl)

        self._lon_entry = Gtk.Entry()
        self._lon_entry.set_placeholder_text("2.3522")
        self._lon_entry.set_size_request(70, -1)
        self._lon_entry.connect("changed", self._on_location_changed)
        loc_row.append(self._lon_entry)
        loc_row.append(Gtk.Label(label="°"))
        outer.append(loc_row)

        # Favorites row (combo + Use — hidden when list is empty)
        self._fav_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self._fav_combo = Gtk.ComboBoxText()
        self._fav_combo.set_hexpand(True)
        self._fav_combo.set_size_request(40, -1)
        self._fav_combo.get_cells()[0].set_property("ellipsize", Pango.EllipsizeMode.END)
        self._fav_row.append(self._fav_combo)

        use_fav_btn = Gtk.Button(label="Use")
        use_fav_btn.set_tooltip_text("Apply this favorite")
        use_fav_btn.connect("clicked", lambda _: self._on_use_favorite())
        self._fav_row.append(use_fav_btn)

        self._fav_row.set_visible(False)
        outer.append(self._fav_row)

        # Save-favorite button — always visible so first favorite can be added
        save_fav_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        save_fav_btn = Gtk.Button(label="★  Save location…")
        save_fav_btn.set_tooltip_text("Save current lat/lon as a named favorite")
        save_fav_btn.set_hexpand(True)
        save_fav_btn.connect("clicked", lambda _: self._on_save_favorite())
        save_fav_row.append(save_fav_btn)
        outer.append(save_fav_row)

        # ── State ─────────────────────────────────────────────────────
        self._current_obj: Optional[DeepSkyObject] = None
        self._ha_timer_id: Optional[int] = None
        self._search_results: list[dict] = []
        self._last_search_name: str = ""

        self._load_persisted()
        self._refresh_favorites()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_persisted(self) -> None:
        if self._client is not None:
            sel_cat, sel_desig, lat, lon = self._client.get_observer()
        else:
            sel_cat, sel_desig, lat, lon = store.load_observer()
        if lat is not None:
            self._lat_entry.set_text(str(lat))
        if lon is not None:
            self._lon_entry.set_text(str(lon))
        if sel_cat:
            self._cat_combo.set_active_id(sel_cat)
        if sel_desig:
            self._obj_entry.set_text(sel_desig)
            self._do_find(sel_cat or "M", sel_desig)

    # ------------------------------------------------------------------
    # Object search
    # ------------------------------------------------------------------

    def _on_catalog_changed(self, _combo: Gtk.ComboBoxText) -> None:
        self._obj_entry.set_text("")
        self._clear_info()

    def _on_entry_changed(self, entry: Gtk.Entry) -> None:
        cat = self._cat_combo.get_active_id() or "M"
        if cat not in ("M", "C"):
            return
        text = entry.get_text().strip()
        if not text or not text.isdigit():
            return
        prefix = "M " if cat == "M" else "C "
        entry.handler_block_by_func(self._on_entry_changed)
        entry.set_text(prefix + text)
        entry.set_position(-1)
        entry.handler_unblock_by_func(self._on_entry_changed)

    def _on_find(self) -> None:
        cat = self._cat_combo.get_active_id() or "M"
        query = self._obj_entry.get_text().strip()
        if not query:
            return
        self._do_find(cat, query)

    def _do_find(self, cat: str, query: str) -> None:
        if self._client is not None:
            obj = self._client.search_object(cat, query)
        else:
            obj = cat_module.find_object(cat, query)
        if obj is None:
            self._info_name.set_markup('<span foreground="red">Not found</span>')
            self._info_type.set_text("")
            self._info_ra.set_text("")
            self._info_dec.set_text("")
            self._current_obj = None
            self._update_ha_visibility()
            return

        self._current_obj = obj
        if self._client is not None:
            self._client.save_selection(cat, obj.designation)
        else:
            store.save_selection(cat, obj.designation)

        if obj.name:
            self._info_name.set_markup(f"<b>{obj.designation}</b> — {obj.name}")
        else:
            self._info_name.set_markup(f"<b>{obj.designation}</b>")
        type_line = obj.obj_type + (f"  ·  {obj.constellation}" if obj.constellation else "")
        self._info_type.set_text(type_line)
        self._info_ra.set_text(f"RA:   {_fmt_ra(obj.ra_deg)}")
        self._info_dec.set_text(f"DEC:  {_fmt_dec(obj.dec_deg)}")
        self._update_ha_visibility()

    # ------------------------------------------------------------------
    # City search
    # ------------------------------------------------------------------

    def _on_search(self) -> None:
        query = self._city_entry.get_text().strip()
        if not query:
            return
        self._search_btn.set_sensitive(False)
        self._search_status.set_text("Searching…")
        self._result_row.set_visible(False)
        threading.Thread(target=self._search_worker, args=(query,), daemon=True).start()

    def _search_worker(self, query: str) -> None:
        try:
            results = _geocode(query)
            GLib.idle_add(self._on_search_done, results)
        except Exception as exc:
            GLib.idle_add(self._on_search_error, str(exc))

    def _on_search_done(self, results: list[dict]) -> bool:
        self._search_btn.set_sensitive(True)
        self._search_results = results
        if not results:
            self._search_status.set_text("No results")
            self._result_row.set_visible(False)
            return GLib.SOURCE_REMOVE

        # Rebuild result combo
        while self._result_combo.get_model() and \
                self._result_combo.get_model().iter_n_children(None) > 0:
            self._result_combo.remove(0)
        for i, r in enumerate(results):
            self._result_combo.append(str(i), r["display_name"])
        self._result_combo.set_active(0)

        n = len(results)
        self._search_status.set_text(f"{n} result{'s' if n != 1 else ''} found")
        self._result_row.set_visible(True)

        # Remember first result's short name for pre-filling the save dialog
        self._last_search_name = results[0].get("display_name", "").split(",")[0].strip()
        return GLib.SOURCE_REMOVE

    def _on_search_error(self, msg: str) -> bool:
        self._search_btn.set_sensitive(True)
        self._search_status.set_text("Search failed")
        self._result_row.set_visible(False)
        return GLib.SOURCE_REMOVE

    def _on_use_result(self) -> None:
        idx_str = self._result_combo.get_active_id()
        if idx_str is None:
            return
        r = self._search_results[int(idx_str)]
        self._apply_latlon(float(r["lat"]), float(r["lon"]))

    # ------------------------------------------------------------------
    # Manual lat/lon
    # ------------------------------------------------------------------

    def _on_location_changed(self, _entry: Gtk.Entry) -> None:
        lat, lon = self._parse_location()
        if self._client is not None:
            self._client.save_location(lat, lon)
        else:
            store.save_location(lat, lon)
        self._update_ha_visibility()

    def _apply_latlon(self, lat: float, lon: float) -> None:
        """Fill lat/lon entries and trigger HA update."""
        self._lat_entry.set_text(f"{lat:.6g}")
        self._lon_entry.set_text(f"{lon:.6g}")
        # _on_location_changed fires via the "changed" signal

    # ------------------------------------------------------------------
    # Favorites
    # ------------------------------------------------------------------

    def _refresh_favorites(self) -> None:
        if self._client is not None:
            favs = self._client.get_favorites()
        else:
            favs = store.load_favorites()
        while self._fav_combo.get_model() and \
                self._fav_combo.get_model().iter_n_children(None) > 0:
            self._fav_combo.remove(0)
        for f in favs:
            label = f"{f['name']} ({f['lat']:.2f}°, {f['lon']:.2f}°)"
            self._fav_combo.append(f["name"], label)
        self._fav_row.set_visible(bool(favs))
        if favs:
            self._fav_combo.set_active(0)

    def _on_use_favorite(self) -> None:
        name = self._fav_combo.get_active_id()
        if name is None:
            return
        if self._client is not None:
            favs = self._client.get_favorites()
        else:
            favs = store.load_favorites()
        for f in favs:
            if f["name"] == name:
                self._apply_latlon(f["lat"], f["lon"])
                break

    def _on_save_favorite(self) -> None:
        lat, lon = self._parse_location()
        if lat is None or lon is None:
            return
        prefill = self._last_search_name
        root = self.get_root()
        dlg = _SaveLocationDialog(
            parent=root,
            prefill=prefill,
            on_saved=lambda name: self._do_save_favorite(name, lat, lon),
        )
        dlg.present()

    def _do_save_favorite(self, name: str, lat: float, lon: float) -> None:
        if self._client is not None:
            self._client.add_favorite(name, lat, lon)
        else:
            store.add_favorite(name, lat, lon)
        self._refresh_favorites()
        # Select the just-saved entry
        self._fav_combo.set_active_id(name)

    # ------------------------------------------------------------------
    # HA ticker
    # ------------------------------------------------------------------

    def _parse_location(self) -> tuple[Optional[float], Optional[float]]:
        try:
            lat = float(self._lat_entry.get_text().strip())
        except ValueError:
            lat = None
        try:
            lon = float(self._lon_entry.get_text().strip())
        except ValueError:
            lon = None
        return lat, lon

    def _update_ha_visibility(self) -> None:
        has_obj = self._current_obj is not None
        self._ha_label.set_visible(has_obj)
        self._alt_label.set_visible(has_obj)
        self._airmass_label.set_visible(has_obj)
        if has_obj:
            self._update_ha()
            if self._ha_timer_id is None:
                self._ha_timer_id = GLib.timeout_add(1000, self._update_ha)
        else:
            if self._ha_timer_id is not None:
                GLib.source_remove(self._ha_timer_id)
                self._ha_timer_id = None

    def _update_ha(self) -> bool:
        if self._current_obj is None:
            return GLib.SOURCE_REMOVE
        lat, lon = self._parse_location()
        if lon is None or lat is None:
            self._ha_label.set_text("HA:   00h 00m 00s")
            self._alt_label.set_text("Alt:  —")
            self._airmass_label.set_text("Airmass:  —")
            return GLib.SOURCE_CONTINUE
        try:
            ha = _compute_ha(self._current_obj.ra_deg, lon)
            alt = _compute_alt(ha, self._current_obj.dec_deg, lat)
            airmass = _compute_airmass(alt)
            self._ha_label.set_text(f"HA:   {_fmt_ha(ha)}  (live)")
            self._alt_label.set_text(f"Alt:  {alt:+.1f}°")
            if airmass is None:
                self._airmass_label.set_text("Airmass:  below horizon")
            else:
                self._airmass_label.set_text(f"Airmass:  {airmass:.2f}")
        except Exception:
            self._ha_label.set_text("HA:   —")
            self._alt_label.set_text("Alt:  —")
            self._airmass_label.set_text("Airmass:  —")
        return GLib.SOURCE_CONTINUE

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_current_object(self) -> Optional[DeepSkyObject]:
        return self._current_obj

    def get_observer_location(self) -> tuple[Optional[float], Optional[float]]:
        return self._parse_location()

    def _clear_info(self) -> None:
        self._current_obj = None
        self._info_name.set_markup("")
        self._info_type.set_text("")
        self._info_ra.set_text("")
        self._info_dec.set_text("")
        self._update_ha_visibility()
