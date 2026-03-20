import ctypes
import platform
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Dict, List

from downloader.converter import ConvertService
from downloader.downloader import DownloadService
from downloader.history import HistoryService
from downloader.models import ConversionItem, DownloadItem, DownloadStatus, OutputFormat
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
        "tab":      ("Segoe UI", 9, "bold"),
        "hist_ts":  ("Segoe UI", 8),
        "hist_fmt": ("Segoe UI", 8, "bold"),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _divider(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(0, 12))


def _format_timestamp(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str).astimezone()
        return dt.strftime("%d/%m/%Y  %H:%M")
    except Exception:
        return iso_str


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
        self.root.title("YouTube Downloader")
        self.root.configure(bg=BG)
        self.root.minsize(580, 580)
        self.root.resizable(True, True)

        # Apply crisp scaling for high-DPI screens
        try:
            self.root.tk.call("tk", "scaling", self.root.winfo_fpixels("1i") / 72)
        except Exception:
            pass

        self.F = _fonts()
        self.service = DownloadService()
        self.history_service = HistoryService()
        self.conv_service = ConvertService()
        self.output_folder = tk.StringVar()
        self.playlist_mode = tk.BooleanVar(value=False)
        self.status_rows: Dict[str, Dict] = {}
        self._placeholder_active = True
        self._current_format = OutputFormat.MP3

        # Converter state
        self._conv_files: List[str] = []
        self._conv_output_folder = tk.StringVar()
        self._conv_format_var = tk.StringVar(value="MP3  —  áudio (192 kbps)")
        self._conv_status_rows: Dict[str, Dict] = {}

        # Format options: label → OutputFormat
        self._format_options = {
            "MP3  —  áudio (192 kbps)":          OutputFormat.MP3,
            "M4A  —  áudio AAC (alta qualidade)": OutputFormat.M4A,
            "MP4  —  vídeo + áudio":              OutputFormat.MP4,
            "WAV  —  sem compressão":             OutputFormat.WAV,
            "OGG  —  áudio Vorbis":               OutputFormat.OGG,
        }
        self._format_var = tk.StringVar(value="MP3  —  áudio (192 kbps)")

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = self.root

        # ── Header ───────────────────────────────────────────────────────────
        header = tk.Frame(root, bg=BG_PANEL)
        header.pack(fill="x")

        accent_bar = tk.Frame(header, bg=ACCENT, width=4)
        accent_bar.pack(side="left", fill="y")

        header_inner = tk.Frame(header, bg=BG_PANEL, padx=20, pady=16)
        header_inner.pack(fill="x", expand=True)

        tk.Label(
            header_inner,
            text="YouTube  →  Downloader",
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

        # ── Tab bar ──────────────────────────────────────────────────────────
        tab_bar = tk.Frame(root, bg=BG_PANEL)
        tab_bar.pack(fill="x")

        self._tab_frames: Dict[str, tk.Frame] = {}
        self._tab_buttons: Dict[str, tk.Label] = {}
        self._active_tab = "download"

        for key, label in [("download", "  ⬇  Download  "), ("converter", "  🔄  Converter  "), ("history", "  📋  Histórico  ")]:
            btn = tk.Label(
                tab_bar,
                text=label,
                bg=BG_PANEL, fg=FG_DIM,
                font=self.F["tab"],
                padx=4, pady=10,
                cursor="hand2",
            )
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            self._tab_buttons[key] = btn

        # Active-tab underline indicator
        self._tab_indicator = tk.Frame(tab_bar, bg=ACCENT, height=2)

        tk.Frame(root, bg=BORDER, height=1).pack(fill="x")

        # ── Content frames (one per tab) ─────────────────────────────────────
        self._download_body   = tk.Frame(root, bg=BG, padx=24, pady=20)
        self._converter_body  = tk.Frame(root, bg=BG, padx=24, pady=20)
        self._history_body    = tk.Frame(root, bg=BG, padx=24, pady=20)

        self._build_download_tab(self._download_body)
        self._build_converter_tab(self._converter_body)
        self._build_history_tab(self._history_body)

        # Show default tab
        self._switch_tab("download")

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _switch_tab(self, name: str):
        self._active_tab = name

        # Update button styles
        for key, btn in self._tab_buttons.items():
            btn.config(fg=FG if key == name else FG_DIM)

        # Move underline indicator
        active_btn = self._tab_buttons[name]
        active_btn.update_idletasks()
        self._tab_indicator.place(
            in_=active_btn,
            relx=0, rely=1.0,
            relwidth=1.0, height=2,
        )

        # Show/hide content
        for key, frame in [("download", self._download_body), ("converter", self._converter_body), ("history", self._history_body)]:
            if key == name:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        if name == "history":
            self._refresh_history()

    # ── Download tab ─────────────────────────────────────────────────────────

    def _build_download_tab(self, body: tk.Frame):
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

        # ── Format selector ──────────────────────────────────────────────────
        fmt_row = tk.Frame(body, bg=BG)
        fmt_row.pack(fill="x", pady=(8, 0))

        tk.Label(
            fmt_row,
            text="Formato de saída:",
            bg=BG, fg=FG_MID,
            font=self.F["label"],
        ).pack(side="left")

        fmt_menu_wrap = tk.Frame(
            fmt_row, bg=BG_INPUT,
            highlightthickness=1, highlightbackground=BORDER,
        )
        fmt_menu_wrap.pack(side="left", padx=(8, 0))

        self._fmt_menu = tk.OptionMenu(
            fmt_menu_wrap,
            self._format_var,
            *self._format_options.keys(),
        )
        self._fmt_menu.config(
            bg=BG_INPUT, fg=FG,
            activebackground=ACCENT, activeforeground="white",
            font=self.F["label"],
            relief="flat", bd=0,
            highlightthickness=0,
            indicatoron=True,
            cursor="hand2",
        )
        self._fmt_menu["menu"].config(
            bg=BG_PANEL, fg=FG,
            activebackground=ACCENT, activeforeground="white",
            font=self.F["label"],
            relief="flat", bd=0,
        )
        self._fmt_menu.pack(padx=4, pady=4)

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

    # ── Converter tab ────────────────────────────────────────────────────────

    def _build_converter_tab(self, body: tk.Frame):
        # ── File input ───────────────────────────────────────────────────────
        self._section_label(body, "ARQUIVOS DE ENTRADA")

        _HoverButton(
            body,
            hover_bg=ACCENT_DK, normal_bg=BG_PANEL,
            text="  Adicionar arquivos…  ",
            command=self._browse_conv_files,
            fg=FG, relief="flat", bd=0,
            activebackground=ACCENT_DK, activeforeground="white",
            font=self.F["btn_sm"],
            cursor="hand2",
        ).pack(anchor="w", pady=(4, 6), ipady=6, ipadx=4)

        file_list_outer = tk.Frame(
            body, bg=BG_INPUT,
            highlightthickness=1, highlightbackground=BORDER,
        )
        file_list_outer.pack(fill="x", pady=(0, 4))

        file_canvas = tk.Canvas(file_list_outer, bg=BG_INPUT, bd=0,
                                highlightthickness=0, height=120)
        file_scroll = ttk.Scrollbar(file_list_outer, orient="vertical",
                                    command=file_canvas.yview)
        self._conv_file_frame = tk.Frame(file_canvas, bg=BG_INPUT)
        self._conv_file_frame.bind(
            "<Configure>",
            lambda e: file_canvas.configure(scrollregion=file_canvas.bbox("all")),
        )
        file_canvas.create_window((0, 0), window=self._conv_file_frame, anchor="nw")
        file_canvas.configure(yscrollcommand=file_scroll.set)
        file_scroll.pack(side="right", fill="y")
        file_canvas.pack(side="left", fill="both", expand=True)

        self._refresh_file_list_ui()

        tk.Label(
            body,
            text="Formatos suportados: MP3, M4A, MP4, WAV, OGG, FLAC e outros",
            bg=BG, fg=FG_DIM,
            font=self.F["label_sm"],
            anchor="w",
        ).pack(anchor="w", pady=(2, 14))

        _divider(body)

        # ── Conversion options ────────────────────────────────────────────────
        self._section_label(body, "OPÇÕES DE CONVERSÃO")

        fmt_row = tk.Frame(body, bg=BG)
        fmt_row.pack(fill="x", pady=(4, 14))

        tk.Label(
            fmt_row,
            text="Formato de saída:",
            bg=BG, fg=FG_MID,
            font=self.F["label"],
        ).pack(side="left")

        fmt_wrap = tk.Frame(fmt_row, bg=BG_INPUT,
                            highlightthickness=1, highlightbackground=BORDER)
        fmt_wrap.pack(side="left", padx=(8, 0))

        conv_fmt_menu = tk.OptionMenu(fmt_wrap, self._conv_format_var,
                                      *self._format_options.keys())
        conv_fmt_menu.config(
            bg=BG_INPUT, fg=FG,
            activebackground=ACCENT, activeforeground="white",
            font=self.F["label"],
            relief="flat", bd=0, highlightthickness=0,
            indicatoron=True, cursor="hand2",
        )
        conv_fmt_menu["menu"].config(
            bg=BG_PANEL, fg=FG,
            activebackground=ACCENT, activeforeground="white",
            font=self.F["label"], relief="flat", bd=0,
        )
        conv_fmt_menu.pack(padx=4, pady=4)

        _divider(body)

        # ── Output folder ─────────────────────────────────────────────────────
        self._section_label(body, "PASTA DE SAÍDA")

        folder_row = tk.Frame(body, bg=BG)
        folder_row.pack(fill="x", pady=(4, 14))

        conv_entry_wrap = tk.Frame(folder_row, bg=BG_INPUT,
                                   highlightthickness=1, highlightbackground=BORDER)
        conv_entry_wrap.pack(side="left", fill="x", expand=True)

        conv_folder_entry = tk.Entry(
            conv_entry_wrap,
            textvariable=self._conv_output_folder,
            font=self.F["input"],
            bg=BG_INPUT, fg=FG,
            insertbackground=FG,
            relief="flat", bd=8, highlightthickness=0,
        )
        conv_folder_entry.pack(fill="x", expand=True)
        conv_folder_entry.bind("<FocusIn>",
            lambda e: conv_entry_wrap.config(highlightbackground=ACCENT))
        conv_folder_entry.bind("<FocusOut>",
            lambda e: conv_entry_wrap.config(highlightbackground=BORDER))

        _HoverButton(
            folder_row,
            hover_bg=ACCENT, normal_bg=BG_PANEL,
            text="  Procurar…  ",
            command=self._browse_conv_folder,
            fg=FG, relief="flat", bd=0,
            activebackground=ACCENT_DK, activeforeground="white",
            font=self.F["btn_sm"],
            cursor="hand2",
        ).pack(side="left", padx=(8, 0), ipady=7, ipadx=4)

        _divider(body)

        # ── Convert button ────────────────────────────────────────────────────
        self._conv_btn = _HoverButton(
            body,
            hover_bg=ACCENT_DK, normal_bg=ACCENT,
            text="🔄   Converter",
            command=self._start_conversion,
            state="disabled",
            fg="white",
            disabledforeground="#4a4a6a",
            relief="flat", bd=0,
            font=self.F["btn"],
            cursor="hand2",
            activebackground=ACCENT_DK, activeforeground="white",
        )
        self._conv_btn.pack(fill="x", ipady=11, pady=(0, 16))

        # ── Status list ───────────────────────────────────────────────────────
        self._section_label(body, "STATUS DAS CONVERSÕES")

        conv_list_outer = tk.Frame(
            body, bg=BG_INPUT,
            highlightthickness=1, highlightbackground=BORDER,
        )
        conv_list_outer.pack(fill="both", expand=True, pady=(4, 0))

        conv_canvas = tk.Canvas(conv_list_outer, bg=BG_INPUT, bd=0, highlightthickness=0)
        conv_scrollbar = ttk.Scrollbar(conv_list_outer, orient="vertical",
                                       command=conv_canvas.yview)
        self._conv_status_frame = tk.Frame(conv_canvas, bg=BG_INPUT)
        self._conv_status_frame.bind(
            "<Configure>",
            lambda e: conv_canvas.configure(scrollregion=conv_canvas.bbox("all")),
        )
        conv_canvas.create_window((0, 0), window=self._conv_status_frame, anchor="nw")
        conv_canvas.configure(yscrollcommand=conv_scrollbar.set)
        conv_scrollbar.pack(side="right", fill="y")
        conv_canvas.pack(side="left", fill="both", expand=True)

        tk.Label(
            self._conv_status_frame,
            text="Nenhuma conversão iniciada",
            bg=BG_INPUT, fg=FG_DIM,
            font=self.F["label"],
            pady=16,
        ).pack()

    def _browse_conv_files(self):
        paths = filedialog.askopenfilenames(
            title="Selecionar arquivos de mídia",
            filetypes=[
                ("Arquivos de mídia",
                 "*.mp3 *.m4a *.mp4 *.wav *.ogg *.flac *.aac *.opus *.mkv *.avi *.mov *.webm"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        for p in paths:
            if p not in self._conv_files:
                self._conv_files.append(p)
        self._refresh_file_list_ui()
        self._update_conv_btn_state()

    def _remove_conv_file(self, path: str):
        if path in self._conv_files:
            self._conv_files.remove(path)
        self._refresh_file_list_ui()
        self._update_conv_btn_state()

    def _refresh_file_list_ui(self):
        for w in self._conv_file_frame.winfo_children():
            w.destroy()

        if not self._conv_files:
            tk.Label(
                self._conv_file_frame,
                text="Nenhum arquivo adicionado",
                bg=BG_INPUT, fg=FG_DIM,
                font=self.F["label"],
                pady=12,
            ).pack()
            return

        for path in self._conv_files:
            name = Path(path).name
            display = name if len(name) <= 55 else name[:52] + "…"

            row = tk.Frame(self._conv_file_frame, bg=BG_PANEL, pady=5, padx=10)
            row.pack(fill="x", pady=(0, 1))

            tk.Label(
                row, text=display,
                bg=BG_PANEL, fg=FG_MID,
                font=self.F["mono_sm"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            _HoverButton(
                row,
                hover_bg=RED, normal_bg=BG_PANEL,
                text=" × ",
                command=lambda p=path: self._remove_conv_file(p),
                fg=FG_DIM, relief="flat", bd=0,
                activebackground=RED, activeforeground="white",
                font=self.F["btn_sm"],
                cursor="hand2",
            ).pack(side="right")

    def _browse_conv_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self._conv_output_folder.set(folder)
            self._update_conv_btn_state()

    def _update_conv_btn_state(self):
        ok = bool(self._conv_files) and bool(self._conv_output_folder.get())
        self._conv_btn["state"] = "normal" if ok else "disabled"

    def _start_conversion(self):
        fmt_label = self._conv_format_var.get()
        output_format = self._format_options.get(fmt_label, OutputFormat.MP3)
        out_dir = self._conv_output_folder.get()

        items = [ConversionItem(input_path=p) for p in self._conv_files]

        for w in self._conv_status_frame.winfo_children():
            w.destroy()
        self._conv_status_rows.clear()

        for item in items:
            self._add_conv_status_row(item)

        self._conv_btn["state"] = "disabled"
        self.conv_service.convert_all(items, out_dir, output_format,
                                      self._on_conv_status_change)

    def _add_conv_status_row(self, item: ConversionItem):
        row = tk.Frame(self._conv_status_frame, bg=BG_PANEL, pady=8, padx=12)
        row.pack(fill="x", padx=0, pady=(0, 1))

        indicator = tk.Frame(row, bg=STATUS_COLOR[item.status], width=3)
        indicator.pack(side="left", fill="y", padx=(0, 10))

        icon_lbl = tk.Label(
            row,
            text=STATUS_ICON[item.status],
            bg=BG_PANEL, fg=STATUS_COLOR[item.status],
            font=self.F["icon"], width=2,
        )
        icon_lbl.pack(side="left")

        name = Path(item.input_path).name
        display = name if len(name) <= 52 else name[:49] + "…"
        tk.Label(
            row, text=display,
            bg=BG_PANEL, fg=FG_MID,
            font=self.F["mono_sm"], anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

        status_lbl = tk.Label(
            row,
            text=item.status.name,
            bg=BG_PANEL, fg=STATUS_COLOR[item.status],
            font=self.F["status"], width=14, anchor="e",
        )
        status_lbl.pack(side="right")

        self._conv_status_rows[item.input_path] = {
            "icon":      icon_lbl,
            "status":    status_lbl,
            "indicator": indicator,
            "item":      item,
        }

    def _on_conv_status_change(self, item: ConversionItem):
        self.root.after(0, lambda: self._update_conv_row(item))

    def _update_conv_row(self, item: ConversionItem):
        row_widgets = self._conv_status_rows.get(item.input_path)
        if not row_widgets:
            return

        color = STATUS_COLOR[item.status]
        row_widgets["icon"].config(text=STATUS_ICON[item.status], fg=color)
        row_widgets["indicator"].config(bg=color)

        label = item.status.name
        if item.error_message:
            short = item.error_message[:38] + ("…" if len(item.error_message) > 38 else "")
            label = f"ERRO: {short}"
        row_widgets["status"].config(text=label, fg=color)

        if item.status in (DownloadStatus.DONE, DownloadStatus.FAILED):
            self._check_conv_all_done()

    def _check_conv_all_done(self):
        terminal = {DownloadStatus.DONE, DownloadStatus.FAILED}
        if self._conv_status_rows and all(
            w["item"].status in terminal for w in self._conv_status_rows.values()
        ):
            self._update_conv_btn_state()

    # ── History tab ──────────────────────────────────────────────────────────

    def _build_history_tab(self, body: tk.Frame):
        # Header row with title + clear button
        top_row = tk.Frame(body, bg=BG)
        top_row.pack(fill="x", pady=(0, 8))

        self._section_label(top_row, "HISTÓRICO DE DOWNLOADS")

        _HoverButton(
            top_row,
            hover_bg=RED, normal_bg=BG_PANEL,
            text="  Limpar tudo  ",
            command=self._clear_history,
            fg=FG_DIM, relief="flat", bd=0,
            activebackground=RED, activeforeground="white",
            font=self.F["btn_sm"],
            cursor="hand2",
        ).pack(side="right", ipady=5, ipadx=4)

        # Scrollable list
        list_outer = tk.Frame(
            body, bg=BG_INPUT,
            highlightthickness=1, highlightbackground=BORDER,
        )
        list_outer.pack(fill="both", expand=True, pady=(4, 0))

        hist_canvas = tk.Canvas(list_outer, bg=BG_INPUT, bd=0, highlightthickness=0)
        hist_scroll = ttk.Scrollbar(list_outer, orient="vertical",
                                    command=hist_canvas.yview)
        self._hist_frame = tk.Frame(hist_canvas, bg=BG_INPUT)

        self._hist_frame.bind(
            "<Configure>",
            lambda e: hist_canvas.configure(scrollregion=hist_canvas.bbox("all")),
        )
        hist_canvas.create_window((0, 0), window=self._hist_frame, anchor="nw")
        hist_canvas.configure(yscrollcommand=hist_scroll.set)

        hist_scroll.pack(side="right", fill="y")
        hist_canvas.pack(side="left", fill="both", expand=True)

        self._hist_empty_label = tk.Label(
            self._hist_frame,
            text="Nenhum download no histórico",
            bg=BG_INPUT, fg=FG_DIM,
            font=self.F["label"],
            pady=16,
        )
        self._hist_empty_label.pack()

    def _refresh_history(self):
        # Clear existing rows
        for w in self._hist_frame.winfo_children():
            w.destroy()

        entries = self.history_service.load()

        if not entries:
            tk.Label(
                self._hist_frame,
                text="Nenhum download no histórico",
                bg=BG_INPUT, fg=FG_DIM,
                font=self.F["label"],
                pady=16,
            ).pack()
            return

        for entry in entries:
            is_done = entry.status == "DONE"
            icon  = "✓" if is_done else "✗"
            color = GREEN if is_done else RED

            row = tk.Frame(self._hist_frame, bg=BG_PANEL, pady=7, padx=12)
            row.pack(fill="x", padx=0, pady=(0, 1))

            # Left accent
            tk.Frame(row, bg=color, width=3).pack(side="left", fill="y", padx=(0, 10))

            # Status icon
            tk.Label(row, text=icon, bg=BG_PANEL, fg=color,
                     font=self.F["icon"], width=2).pack(side="left")

            # Format badge
            tk.Label(
                row, text=entry.fmt,
                bg=BG_INPUT, fg=ACCENT,
                font=self.F["hist_fmt"],
                padx=5, pady=2,
            ).pack(side="left", padx=(6, 0))

            # Title / URL
            display = entry.title if entry.title != entry.url else entry.url
            if len(display) > 50:
                display = display[:47] + "…"
            tk.Label(
                row, text=display,
                bg=BG_PANEL, fg=FG_MID,
                font=self.F["mono_sm"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=(8, 0))

            # Timestamp
            tk.Label(
                row,
                text=_format_timestamp(entry.timestamp),
                bg=BG_PANEL, fg=FG_DIM,
                font=self.F["hist_ts"],
            ).pack(side="right")

    def _clear_history(self):
        self.history_service.clear()
        self._refresh_history()

    # ── Section label ─────────────────────────────────────────────────────────

    def _section_label(self, parent, text: str):
        tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"), fg=FG_DIM,
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

        fmt_label = self._format_var.get()
        self._current_format = self._format_options.get(fmt_label, OutputFormat.MP3)

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
            output_format=self._current_format,
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

        # Persist to history when download is settled
        if item.status in (DownloadStatus.DONE, DownloadStatus.FAILED):
            self.history_service.record(item, self._current_format)
            if self._active_tab == "history":
                self._refresh_history()


def main():
    _fix_dpi()
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
