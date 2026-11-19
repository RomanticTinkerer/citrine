"""Terminal form: fill in the boxes, press Enter on Download. `citrine --tui`"""
import curses
import os
import threading

from .download import submit

LABELS = ("Link or lichess:name / chesscom:name", "Save into folder", "From (2020, 2020-05, 2020-05-17)", "To (same formats)", "Max games (blank = all)")
HELP = "Tab or arrows move, Enter goes on, Ctrl+U clears a box, Esc quits. Several links: separate with spaces."


def _loop(scr, folder):
    curses.curs_set(1)
    values, i, lines = ["", folder, "", "", ""], 0, []
    state = {"busy": False, "note": ""}
    last = len(values)  # index of the Download button

    def work():
        def progress(done, total):
            state["note"] = f"Downloading... {done}/{total} games"

        state["note"] = "Downloading..."
        lines[:] = submit(values, progress)
        state.update(busy=False, note="")

    while True:
        scr.erase()
        h, w = scr.getmaxyx()
        put = lambda y, x, s, attr=0: y < h - 1 and x < w and scr.addnstr(y, x, s, max(0, w - x - 1), attr)
        put(0, 2, "citrine: download chess games", curses.A_BOLD)
        for n, (label, val) in enumerate(zip(LABELS, values)):
            put(2 + n * 2, 2, label)
            put(3 + n * 2, 2, f"[ {val[-(w - 10):] if w > 12 else val} ]", curses.A_REVERSE if n == i else 0)
        put(13, 2, "[ Download ]", curses.A_REVERSE if i == last else curses.A_BOLD)
        put(15, 2, state["note"] or "Ready.", curses.A_DIM)
        for n, line in enumerate(lines[: h - 19]):
            put(17 + n, 2, line)
        put(h - 1, 0, HELP[: w - 1], curses.A_DIM) if h > 1 else None
        if i < last and not state["busy"]:
            scr.move(3 + i * 2, min(w - 3, 4 + len(values[i][-(w - 10):])))
        scr.refresh()
        scr.timeout(150)
        k = scr.getch()
        if state["busy"] or k == -1:
            continue
        if k == 27:
            return
        if k in (9, curses.KEY_DOWN):
            i = (i + 1) % (last + 1)
        elif k in (curses.KEY_BTAB, curses.KEY_UP):
            i = (i - 1) % (last + 1)
        elif k in (10, 13, curses.KEY_ENTER):
            if i == last:
                state["busy"] = True
                threading.Thread(target=work, daemon=True).start()
            else:
                i += 1
        elif i < last and k in (curses.KEY_BACKSPACE, 127, 8):
            values[i] = values[i][:-1]
        elif i < last and k == 21:  # Ctrl+U
            values[i] = ""
        elif i < last and 32 <= k < 127:
            values[i] += chr(k)


def main(folder="CitrineData"):
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(_loop, folder)
