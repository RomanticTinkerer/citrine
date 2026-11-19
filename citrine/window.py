"""GTK4 + libadwaita window: paste a link, pick a folder, press Download. `citrine-gui`

Needs the system's PyGObject (python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1)."""
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .download import submit  # noqa: E402

APP_ID = "io.github.romantictinkerer.Citrine"


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Citrine", default_width=500, default_height=560)
        self.folder = str(Path.home() / "CitrineData")

        self.link = Adw.EntryRow(title="Link, or lichess:name / chesscom:name")
        self.link.connect("entry-activated", self.start)
        self.where = Adw.ActionRow(title="Save into", subtitle=self.folder, subtitle_lines=1)
        pick = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Choose folder")
        pick.add_css_class("flat")
        pick.connect("clicked", self.choose_folder)
        self.where.add_suffix(pick)

        source = Adw.PreferencesGroup(title="Download chess games", description="Lichess and Chess.com, including old and daily games.")
        source.add(self.link)
        source.add(self.where)

        self.since = Adw.EntryRow(title="From (2020, 2020-05 or 2020-05-17)")
        self.until = Adw.EntryRow(title="To (same formats)")
        self.limit = Adw.SpinRow.new_with_range(0, 1_000_000, 100)
        self.limit.set_title("Max games (0 = all, newest first)")
        rng = Adw.PreferencesGroup(title="Range (optional)")
        for row in (self.since, self.until, self.limit):
            rng.add(row)

        self.button = Gtk.Button(label="Download", halign=Gtk.Align.CENTER)
        self.button.add_css_class("suggested-action")
        self.button.add_css_class("pill")
        self.button.connect("clicked", self.start)
        self.bar = Gtk.ProgressBar(visible=False)
        self.out = Gtk.Label(wrap=True, xalign=0, selectable=True, margin_top=6)
        self.out.add_css_class("dim-label")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, margin_top=12, margin_bottom=24, margin_start=18, margin_end=18)
        for w in (source, rng, self.button, self.bar, self.out):
            box.append(w)
        clamp = Adw.Clamp(maximum_size=560, child=box)
        scroll = Gtk.ScrolledWindow(child=clamp, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        view = Adw.ToolbarView(content=scroll)
        view.add_top_bar(Adw.HeaderBar())
        self.toasts = Adw.ToastOverlay(child=view)
        self.set_content(self.toasts)

    def choose_folder(self, _button):
        dialog = Gtk.FileDialog(title="Save games into")
        if Path(self.folder).exists():
            dialog.set_initial_folder(Gio.File.new_for_path(self.folder))
        dialog.select_folder(self, None, self.folder_chosen)

    def folder_chosen(self, dialog, result):
        try:
            path = dialog.select_folder_finish(result).get_path()
        except GLib.Error:  # dialog closed without choosing
            return
        self.folder = path
        self.where.set_subtitle(path)

    def start(self, *_):
        if not self.button.get_sensitive():
            return
        values = [self.link.get_text(), self.folder, self.since.get_text(), self.until.get_text(), str(int(self.limit.get_value()) or "")]
        self.button.set_sensitive(False)
        self.bar.set_visible(True)
        self.bar.pulse()
        self.out.set_label("Downloading... big accounts can take a few minutes.")
        self.pulse = GLib.timeout_add(150, lambda: (self.bar.pulse(), True)[1])
        threading.Thread(target=self.work, args=(values,), daemon=True).start()

    def work(self, values):
        def progress(done, total):
            GLib.idle_add(self.out.set_label, f"Downloading... {done}/{total} games")

        GLib.idle_add(self.finish, submit(values, progress))

    def finish(self, lines):
        GLib.source_remove(self.pulse)
        self.bar.set_visible(False)
        self.button.set_sensitive(True)
        self.out.set_label("\n".join(lines))
        self.toasts.add_toast(Adw.Toast(title=lines[0][:80], timeout=5))


def main():
    app = Adw.Application(application_id=APP_ID)
    app.connect("activate", lambda a: Window(a).present())
    return app.run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
