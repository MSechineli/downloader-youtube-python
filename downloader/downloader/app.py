import ctypes
import platform
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Dict

from downloader.downloader import DownloadService
from downloader.models import DownloadItem, DownloadStatus
from downloader.url_parser import parse_urls_to_items


# ── DPI fix (must run before Tk() is created) ────────────────────────────────

def _fix_dpi():
    """Prevent blurry text on Windows and high-DPI displays."""
    if platform.system() == "Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # per-monitor v2
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


# ── Palette ──────────────────────────────────────────────────────────────────

BG        = "#16161f"
BG_PANEL  = "#1e1e2b"
BG_INPUT  = "#12121a"
BG_HOVER  = "#252535"
ACCENT    = "#7c6af7"
ACCENT_DK = "#6254d4"
BORDER    = "#2e2e42"
FG        = "#dcdcf0"
FG_DIM    = "#6b6d88"
FG_MID    = "#9a9bb8"
GREEN     = "#4ade80"
RED       = "#f87171"
YELLOW    = "#fbbf24"

STATUS_COLOR = {
    DownloadStatus.PENDING:     FG_DIM,
    DownloadStatus.IN_PROGRESS: YELLOW,
    DownloadStatus.DONE:        GREEN,
    DownloadStatus.FAILED:      RED,
}

STATUS_ICON = {
    DownloadStatus.PENDING:     "○",
    DownloadStatus.IN_PROGRESS: "↓",
    DownloadStatus.DONE:        "✓",
    DownloadStatus.FAILED:      "✗",
}

# ── Font definitions (defined after Tk init so scaling is applied) ───────────

def _fonts():
    return {
        "title":    ("Segoe UI", 13, "bold"),
        "label":    ("Segoe UI", 9),
        "label_sm": ("Segoe UI", 8),
        "input":    ("Consolas", 10),
        "btn":      ("Segoe UI", 10, "bold"),
        "btn_sm":   ("Segoe UI", 9),
        "icon":     ("Segoe UI", 13, "bold"),
        "mono_sm":  ("Consolas", 9),
        "status":   ("Segoe UI", 9, "bold"),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _divider(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(0, 12))


class _HoverButton(tk.Button):
    """Button that changes background on hover."""
    def __init__(self, master, hover_bg, normal_bg, **kw):
        super().__init__(master, bg=normal_bg, **kw)
        self._normal = normal_bg
        self._hover  = hover_bg
        self.bind("<Enter>", lambda _: self.config(bg=self._hover))
        self.bind("<Leave>", lambda _: self.config(bg=self._normal))


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("YouTube → MP3")
        self.root.configure(bg=BG)
        self.root.minsize(580, 540)
        self.root.resizable(True, True)

        # Apply crisp scaling for high-DPI screens
        try:
            self.root.tk.call("tk", "scaling", self.root.winfo_fpixels("1i") / 72)
        except Exception:
            pass

        self.F = _fonts()
        self.service = DownloadService()
        self.output_folder = tk.StringVar()
        self.playlist_mode = tk.BooleanVar(value=False)
        self.status_rows: Dict[str, Dict] = {}
        self._placeholder_active = True

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = self.root

        # ── Sidebar accent bar + header ──────────────────────────────────────
        header = tk.Frame(root, bg=BG_PANEL)
        header.pack(fill="x")

        accent_bar = tk.Frame(header, bg=ACCENT, width=4)
        accent_bar.pack(side="left", fill="y")

        header_inner = tk.Frame(header, bg=BG_PANEL, padx=20, pady=16)
        header_inner.pack(fill="x", expand=True)

        tk.Label(
            header_inner,
            text="YouTube  →  MP3",
            bg=BG_PANEL, fg=FG,
            font=self.F["title"],
            anchor="w",
        ).pack(side="left")

        tk.Label(
            header_inner,
            text="downloader",
            bg=BG_PANEL, fg=FG_DIM,
            font=self.F["label"],
            anchor="e",
        ).pack(side="right", padx=(0, 2))

        tk.Frame(root, bg=ACCENT, height=2).pack(fill="x")  # accent underline

        # ── Body ─────────────────────────────────────────────────────────────
        body = tk.Frame(root, bg=BG, padx=24, pady=20)
        body.pack(fill="both", expand=True)

        # ── URL section ──────────────────────────────────────────────────────
        self._section_label(body, "LINKS DO YOUTUBE")

        url_wrap = tk.Frame(
            body, bg=BG_INPUT,
            highlightthickness=1, highlightbackground=BORDER,
        )
        url_wrap.pack(fill="x", pady=(4, 4))

        self.url_text = tk.Text(
            url_wrap, height=5,
            bg=BG_INPUT, fg=FG,
            insertbackground=FG,
            relief="flat", bd=10,
            font=self.F["input"],
            wrap="none",
            selectbackground=ACCENT,
            selectforeground="white",
        )
        self.url_text.pack(fill="both", expand=True)
        self.url_text.bind("<KeyRelease>", lambda e: self._on_url_change())
        self.url_text.bind("<FocusIn>",    self._clear_placeholder)
        self.url_text.bind("<FocusOut>",   self._restore_placeholder)
        self.url_text.bind("<FocusIn>",
            lambda e: url_wrap.config(highlightbackground=ACCENT), add="+")
        self.url_text.bind("<FocusOut>",
            lambda e: url_wrap.config(highlightbackground=BORDER), add="+")

        placeholder = "Cole um link por linha…"
        self.url_text.insert("1.0", placeholder)
        self.url_text.config(fg=FG_DIM)

        tk.Label(
            body,
            text="Um link por linha. Formatos aceitos: youtube.com/watch, youtu.be, youtube.com/shorts",
            bg=BG, fg=FG_DIM,
            font=self.F["label_sm"],
            anchor="w",
        ).pack(anchor="w", pady=(2, 14))

        _divider(body)

        # ── Options ──────────────────────────────────────────────────────────
        self._section_label(body, "OPÇÕES")

        opts = tk.Frame(body, bg=BG)
        opts.pack(fill="x", pady=(4, 14))

        cb_frame = tk.Frame(opts, bg=BG_PANEL,
                            highlightthickness=1, highlightbackground=BORDER)
        cb_frame.pack(side="left")

        self.playlist_cb = tk.Checkbutton(
            cb_frame,
            text="  Baixar playlist inteira",
            variable=self.playlist_mode,
            bg=BG_PANEL, fg=FG,
            selectcolor=ACCENT,
            activebackground=BG_PANEL, activeforeground=FG,
            font=self.F["label"],
            bd=0, highlightthickness=0,
            padx=10, pady=7,
            cursor="hand2",
        )
        self.playlist_cb.pack()

        tk.Label(
            opts,
            text="  desmarcado = apenas o vídeo do link",
            bg=BG, fg=FG_DIM, font=self.F["label_sm"],
        ).pack(side="left", padx=10)

        _divider(body)

        # ── Output folder ────────────────────────────────────────────────────
        self._section_label(body, "PASTA DE SAÍDA")

        folder_row = tk.Frame(body, bg=BG)
        folder_row.pack(fill="x", pady=(4, 14))

        entry_wrap = tk.Frame(
            folder_row, bg=BG_INPUT,
            highlightthickness=1, highlightbackground=BORDER,
        )
        entry_wrap.pack(side="left", fill="x", expand=True)

        self.folder_entry = tk.Entry(
            entry_wrap,
            textvariable=self.output_folder,
            font=self.F["input"],
            bg=BG_INPUT, fg=FG,
            insertbackground=FG,
            relief="flat", bd=8,
            highlightthickness=0,
        )
        self.folder_entry.pack(fill="x", expand=True)
        self.folder_entry.bind("<FocusIn>",
            lambda e: entry_wrap.config(highlightbackground=ACCENT))
        self.folder_entry.bind("<FocusOut>",
            lambda e: entry_wrap.config(highlightbackground=BORDER))

        _HoverButton(
            folder_row,
            hover_bg=ACCENT, normal_bg=BG_PANEL,
            text="  Procurar…  ",
            command=self._browse_folder,
            fg=FG, relief="flat", bd=0,
            activebackground=ACCENT_DK, activeforeground="white",
            font=self.F["btn_sm"],
            cursor="hand2",
        ).pack(side="left", padx=(8, 0), ipady=7, ipadx=4)

        _divider(body)

        # ── Download button ──────────────────────────────────────────────────
        self.download_btn = _HoverButton(
            body,
            hover_bg=ACCENT_DK, normal_bg=ACCENT,
            text="⬇   Baixar",
            command=self._start_download,
            state="disabled",
            fg="white",
            disabledforeground="#4a4a6a",
            relief="flat", bd=0,
            font=self.F["btn"],
            cursor="hand2",
            activebackground=ACCENT_DK,
            activeforeground="white",
        )
        self.download_btn.pack(fill="x", ipady=11, pady=(0, 16))

        # ── Status list ──────────────────────────────────────────────────────
        self._section_label(body, "STATUS DOS DOWNLOADS")

        list_outer = tk.Frame(
            body, bg=BG_INPUT,
            highlightthickness=1, highlightbackground=BORDER,
        )
        list_outer.pack(fill="both", expand=True, pady=(4, 0))

        canvas = tk.Canvas(list_outer, bg=BG_INPUT, bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_outer, orient="vertical",
                                  command=canvas.yview)
        self.status_frame = tk.Frame(canvas, bg=BG_INPUT)

        self.status_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.status_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._canvas = canvas

        # empty-state hint
        self._empty_label = tk.Label(
            self.status_frame,
            text="Nenhum download iniciado",
            bg=BG_INPUT, fg=FG_DIM,
            font=self.F["label"],
            pady=16,
        )
        self._empty_label.pack()

    # ── Section label ─────────────────────────────────────────────────────────

    def _section_label(self, parent, text: str):
        tk.Label(
            parent,
            text=text,
            bg=BG, fg=FG_DIM,
            font=("Segoe UI", 7, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 2))

    # ── Placeholder helpers ────────────────────────────────────────────────────

    def _clear_placeholder(self, _event=None):
        if self._placeholder_active:
            self.url_text.delete("1.0", "end")
            self.url_text.config(fg=FG)
            self._placeholder_active = False

    def _restore_placeholder(self, _event=None):
        if not self.url_text.get("1.0", "end-1c").strip():
            self.url_text.insert("1.0", "Cole um link por linha…")
            self.url_text.config(fg=FG_DIM)
            self._placeholder_active = True

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _on_url_change(self):
        has_urls = not self._placeholder_active and bool(
            self.url_text.get("1.0", "end-1c").strip()
        )
        has_folder = bool(self.output_folder.get())
        self.download_btn["state"] = "normal" if (has_urls and has_folder) else "disabled"

    def _browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)
            self._on_url_change()

    def _start_download(self):
        self._clear_placeholder()
        text = self.url_text.get("1.0", "end-1c")
        items = parse_urls_to_items(text, validate=True)
        out_dir = self.output_folder.get()

        for widget in self.status_frame.winfo_children():
            widget.destroy()
        self.status_rows.clear()

        for item in items:
            self._add_status_row(item)

        self.download_btn["state"] = "disabled"
        self.service.download_all(
            items, out_dir,
            self._on_status_change,
            playlist=self.playlist_mode.get(),
        )

    def _add_status_row(self, item: DownloadItem):
        row = tk.Frame(self.status_frame, bg=BG_PANEL, pady=8, padx=12)
        row.pack(fill="x", padx=0, pady=(0, 1))

        # left accent indicator
        indicator = tk.Frame(row, bg=STATUS_COLOR[item.status], width=3)
        indicator.pack(side="left", fill="y", padx=(0, 10))

        # icon
        icon_lbl = tk.Label(
            row,
            text=STATUS_ICON[item.status],
            bg=BG_PANEL,
            fg=STATUS_COLOR[item.status],
            font=self.F["icon"],
            width=2,
        )
        icon_lbl.pack(side="left")

        # url
        url_short = item.url if len(item.url) <= 52 else item.url[:49] + "…"
        url_lbl = tk.Label(
            row, text=url_short,
            bg=BG_PANEL, fg=FG_MID,
            font=self.F["mono_sm"],
            anchor="w",
        )
        url_lbl.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # status badge
        status_lbl = tk.Label(
            row,
            text=item.status.name,
            bg=BG_PANEL,
            fg=STATUS_COLOR[item.status],
            font=self.F["status"],
            width=14,
            anchor="e",
        )
        status_lbl.pack(side="right")

        self.status_rows[item.url] = {
            "icon":      icon_lbl,
            "status":    status_lbl,
            "indicator": indicator,
            "row":       row,
        }

    def _on_status_change(self, item: DownloadItem):
        self.root.after(0, lambda: self._update_row(item))

    def _update_row(self, item: DownloadItem):
        row_widgets = self.status_rows.get(item.url)
        if not row_widgets:
            return
        color = STATUS_COLOR[item.status]
        icon  = STATUS_ICON[item.status]

        row_widgets["icon"].config(text=icon, fg=color)
        row_widgets["indicator"].config(bg=color)

        label = item.status.name
        if item.error_message:
            short_err = item.error_message[:38] + ("…" if len(item.error_message) > 38 else "")
            label = f"ERRO: {short_err}"
        row_widgets["status"].config(text=label, fg=color)


def main():
    _fix_dpi()
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
