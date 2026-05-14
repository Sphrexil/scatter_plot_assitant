"""
散点图工具 —— 生成可直接复制到 CorelDRAW 的矢量图元文件

功能:
  - 从 CSV / 手动输入加载数据
  - 自定义 XY 列、分组、颜色、标记、标签
  - 添加趋势线、误差棒
  - 导出 SVG / PDF / PNG
  - 复制矢量图到剪贴板（SVG 格式，可直接粘贴到 CDR）
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox, font
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib import ticker as mpl_ticker
import matplotlib.ticker as ticker
import io
import os
import re
import webbrowser

# ---------- Windows clipboard helpers ----------
try:
    import win32clipboard as wc
    import win32con
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

WMF_ENABLED = False  # set True if you install svg2emf / Pillow + cairo


def copy_svg_to_clipboard(svg_bytes: bytes):
    """Put raw SVG text onto clipboard as CF_TEXT (CDR accepts SVG paste)."""
    if not _HAS_WIN32:
        return False
    try:
        wc.OpenClipboard()
        wc.EmptyClipboard()
        wc.SetClipboardData(win32con.CF_TEXT, svg_bytes)
        wc.CloseClipboard()
        return True
    except Exception:
        return False


def copy_emf_to_clipboard(emf_bytes: bytes):
    """Put EMF data onto clipboard as CF_ENHMETAFILE."""
    if not _HAS_WIN32:
        return False
    try:
        import ctypes
        from ctypes import windll

        # Write to temp file and load as EMF handle
        tmp = os.path.join(os.environ["TEMP"], "_lunzi_emf_check.emf")
        with open(tmp, "wb") as f:
            f.write(emf_bytes)
        hemf = windll.gdi32.GetEnhMetaFileW(tmp)
        if not hemf:
            return False
        wc.OpenClipboard()
        wc.EmptyClipboard()
        wc.SetClipboardData(win32con.CF_ENHMETAFILE, hemf)
        wc.CloseClipboard()
        windll.gdi32.DeleteEnhMetaFile(hemf)
        os.remove(tmp)
        return True
    except Exception:
        return False


# ---------- Main Application ----------
class ScatterTool:
    def __init__(self):
        self.root = ttk.Window(themename="flatly")
        self.root.title("散点图工具 · Scatter → CDR")
        self.root.geometry("1280x860")
        self.root.minsize(960, 640)

        # data
        self.df: pd.DataFrame | None = None
        self.status_var = tk.StringVar(value="就绪 · Ready [v4]")
        self.group_colors: dict[str, str] = {}  # group name → hex color
        self.palettes: list[dict] = []          # [{"name": "...", "colors": [...]}, ...]
        self.current_palette_name = ""
        self._load_palettes()

        self._build_ui()
        self._bind_events()

    # ========== UI ==========
    def _build_ui(self):
        # -- top toolbar --
        toolbar = ttk.Frame(self.root, padding=(8, 4))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="📂 打开 CSV", command=self.load_csv, bootstyle="outline-primary").pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="✏️ 手动输入", command=self.manual_input, bootstyle="outline-secondary").pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📋 从剪贴板粘贴", command=self.paste_from_clipboard, bootstyle="outline-secondary").pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(toolbar, text="📄 导出 SVG", command=lambda: self.export("svg"), bootstyle="outline-info").pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📄 导出 PDF", command=lambda: self.export("pdf"), bootstyle="outline-info").pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🖼️ 导出 PNG", command=lambda: self.export("png"), bootstyle="outline-info").pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        self.svg_btn = ttk.Button(toolbar, text="📋 复制 SVG 到剪贴板（CDR 粘贴）", command=self.copy_to_clipboard, bootstyle="warning")
        self.svg_btn.pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(toolbar, textvariable=self.status_var, foreground="#555").pack(side=tk.RIGHT, padx=8)

        # -- main paned window --
        paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=2)

        # left: plot
        self._plot_frame = ttk.Frame(paned)
        paned.add(self._plot_frame, weight=3)

        # right: config panel
        cfg_frame = ttk.Frame(paned, width=260)
        paned.add(cfg_frame, weight=1)

        self._build_plot_area()
        self._build_config_panel(cfg_frame)

    def _build_plot_area(self):
        self.fig = Figure(figsize=(8, 6.2), dpi=120, facecolor="#ffffff")
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self._plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # toolbar
        tb = NavigationToolbar2Tk(self.canvas, self._plot_frame)
        tb.update()

    def _build_config_panel(self, parent):
        f = ttk.Frame(parent, padding=(6, 4))
        f.pack(fill=tk.BOTH, expand=True)

        row = 0
        # ---------- Mode switch ----------
        self.mode_var = tk.StringVar(value="scatter")
        mode_frame = ttk.LabelFrame(f, text="图表模式")
        mode_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 4))
        ttk.Radiobutton(mode_frame, text="散点图 (X/Y)", variable=self.mode_var,
                        value="scatter", command=self._on_mode_switch).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(mode_frame, text="三元图 (A/B/C)", variable=self.mode_var,
                        value="ternary", command=self._on_mode_switch).pack(side=tk.LEFT, padx=2)
        row += 1

        # ---------- Column mapping: Scatter ----------
        self._scatter_cols_frame = ttk.Frame(f)
        self._scatter_cols_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW)
        ttk.Label(self._scatter_cols_frame, text="列映射 (散点)",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        sf = ttk.Frame(self._scatter_cols_frame)
        sf.pack(fill=tk.X)
        r2 = 0
        ttk.Label(sf, text="X 列:").grid(row=r2, column=0, sticky=tk.W, pady=1)
        self.col_x = ttk.Combobox(sf, state="readonly", width=18)
        self.col_x.grid(row=r2, column=1, sticky=tk.EW, pady=1); r2 += 1
        ttk.Label(sf, text="Y 列:").grid(row=r2, column=0, sticky=tk.W, pady=1)
        self.col_y = ttk.Combobox(sf, state="readonly", width=18)
        self.col_y.grid(row=r2, column=1, sticky=tk.EW, pady=1); r2 += 1
        ttk.Label(sf, text="分组列（可选）:").grid(row=r2, column=0, sticky=tk.W, pady=1)
        self.col_g = ttk.Combobox(sf, state="readonly", width=18)
        self.col_g.grid(row=r2, column=1, sticky=tk.EW, pady=1); r2 += 1
        sf.grid_columnconfigure(1, weight=1)
        row += 1

        # ---------- Column mapping: Ternary ----------
        self._ternary_cols_frame = ttk.Frame(f)
        self._ternary_cols_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW)
        ttk.Label(self._ternary_cols_frame, text="列映射 (三元)",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        tf = ttk.Frame(self._ternary_cols_frame)
        tf.pack(fill=tk.X)
        r3 = 0
        ttk.Label(tf, text="组分 A:").grid(row=r3, column=0, sticky=tk.W, pady=1)
        self.col_a = ttk.Combobox(tf, state="readonly", width=18)
        self.col_a.grid(row=r3, column=1, sticky=tk.EW, pady=1); r3 += 1
        ttk.Label(tf, text="组分 B:").grid(row=r3, column=0, sticky=tk.W, pady=1)
        self.col_b = ttk.Combobox(tf, state="readonly", width=18)
        self.col_b.grid(row=r3, column=1, sticky=tk.EW, pady=1); r3 += 1
        ttk.Label(tf, text="组分 C:").grid(row=r3, column=0, sticky=tk.W, pady=1)
        self.col_c = ttk.Combobox(tf, state="readonly", width=18)
        self.col_c.grid(row=r3, column=1, sticky=tk.EW, pady=1); r3 += 1
        ttk.Label(tf, text="分组列（可选）:").grid(row=r3, column=0, sticky=tk.W, pady=1)
        self.col_g2 = ttk.Combobox(tf, state="readonly", width=18)
        self.col_g2.grid(row=r3, column=1, sticky=tk.EW, pady=1); r3 += 1
        tf.grid_columnconfigure(1, weight=1)
        self._ternary_cols_frame.grid_remove()
        row += 1

        ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2,
                                                     sticky=tk.EW, pady=6)
        row += 1

        # ---------- Appearance ----------
        ttk.Label(f, text="外观设置", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2,
                                                                        sticky=tk.W, pady=(0, 4))
        row += 1

        ttk.Label(f, text="标记大小:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.marker_size = ttk.Spinbox(f, from_=10, to=1000, width=6, value=125)
        self.marker_size.grid(row=row, column=1, sticky=tk.W, pady=1)
        row += 1

        ttk.Label(f, text="透明度:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.alpha = ttk.Spinbox(f, from_=0.1, to=1.0, increment=0.1, width=6, value=1.0,
                                 format="%.1f")
        self.alpha.grid(row=row, column=1, sticky=tk.W, pady=1)
        row += 1

        # ---------- Axis range ----------
        ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2,
                                                     sticky=tk.EW, pady=6)
        row += 1
        ttk.Label(f, text="轴起始值 (可选)", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2,
                                                                               sticky=tk.W, pady=(0, 4))
        row += 1
        ttk.Label(f, text="X 起始值:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.xy_start_x = ttk.Entry(f, width=20)
        self.xy_start_x.grid(row=row, column=1, sticky=tk.EW, pady=1)
        row += 1
        ttk.Label(f, text="Y 起始值:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.xy_start_y = ttk.Entry(f, width=20)
        self.xy_start_y.grid(row=row, column=1, sticky=tk.EW, pady=1)
        row += 1

        # ---------- Regression ----------
        ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2,
                                                     sticky=tk.EW, pady=6)
        row += 1
        ttk.Label(f, text="拟合线", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2,
                                                                       sticky=tk.W, pady=(0, 4))
        row += 1
        self.show_reg = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="显示趋势线", variable=self.show_reg, command=self._auto_plot).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=1)
        row += 1

        ttk.Label(f, text="阶数:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.reg_order = ttk.Spinbox(f, from_=1, to=6, width=6, value=1)
        self.reg_order.grid(row=row, column=1, sticky=tk.W, pady=1)
        row += 1

        # ---------- Point outline ----------
        self.show_outline = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="散点轮廓线", variable=self.show_outline, command=self._auto_plot).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=1)
        row += 1

        # ---------- Labels ----------
        ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2,
                                                     sticky=tk.EW, pady=6)
        row += 1
        ttk.Label(f, text="标签与标题", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2,
                                                                         sticky=tk.W, pady=(0, 4))
        row += 1

        ttk.Label(f, text="X 轴标签:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.label_x = ttk.Entry(f, width=20)
        self.label_x.grid(row=row, column=1, sticky=tk.EW, pady=1)
        row += 1

        ttk.Label(f, text="Y 轴标签:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.label_y = ttk.Entry(f, width=20)
        self.label_y.grid(row=row, column=1, sticky=tk.EW, pady=1)
        row += 1

        ttk.Label(f, text="标题:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.title = ttk.Entry(f, width=20)
        self.title.grid(row=row, column=1, sticky=tk.EW, pady=1)
        row += 1

        # ---------- Group colors ----------
        self._color_lf = ttk.LabelFrame(f, text="分组颜色")
        self._color_lf.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 4))

        # palette selector row
        pal_row = ttk.Frame(self._color_lf)
        pal_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(pal_row, text="色板:").pack(side=tk.LEFT, padx=(0, 4))
        self._palette_combo = ttk.Combobox(pal_row, state="readonly", width=12)
        self._palette_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._palette_combo.bind("<<ComboboxSelected>>", self._on_palette_change)
        btn_frame = ttk.Frame(self._color_lf)
        btn_frame.pack(fill=tk.X, pady=(0, 2))
        ttk.Button(btn_frame, text="➕ 新建", command=self._on_new_palette).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="🗑 删除", command=self._on_delete_palette).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="📂 导入", command=self._on_import_palettes).pack(side=tk.LEFT, padx=1)

        self._color_inner = ttk.Frame(self._color_lf)
        self._color_inner.pack(fill=tk.X, pady=2)
        row += 1

        # ---------- Figure size ----------
        ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2,
                                                     sticky=tk.EW, pady=6)
        row += 1
        ttk.Label(f, text="图幅尺寸 (inch)", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2,
                                                                              sticky=tk.W, pady=(0, 4))
        row += 1
        ttk.Label(f, text="宽度:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.fig_w = ttk.Spinbox(f, from_=3, to=30, width=6, value=8)
        self.fig_w.grid(row=row, column=1, sticky=tk.W, pady=1)
        row += 1
        ttk.Label(f, text="高度:").grid(row=row, column=0, sticky=tk.W, pady=1)
        self.fig_h = ttk.Spinbox(f, from_=2, to=30, width=6, value=6.2)
        self.fig_h.grid(row=row, column=1, sticky=tk.W, pady=1)
        row += 1

        # ---------- Update button ----------
        ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2,
                                                     sticky=tk.EW, pady=6)
        row += 1
        self.update_btn = ttk.Button(f, text="🔄 更新绘图", command=self._auto_plot, bootstyle="success")
        self.update_btn.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=4)

        # stretch
        f.grid_columnconfigure(1, weight=1)

        # init palette combo
        self._refresh_palette_combo()

    def _bind_events(self):
        for w in (self.marker_size, self.alpha, self.reg_order, self.fig_w, self.fig_h,
                  self.xy_start_x, self.xy_start_y):
            w.bind("<KeyRelease>", lambda e: self._schedule_plot())
        for w in (self.label_x, self.label_y, self.title):
            w.bind("<KeyRelease>", lambda e: self._schedule_plot())
        for w in (self.col_x, self.col_y, self.col_g, self.col_a, self.col_b, self.col_c, self.col_g2):
            w.bind("<<ComboboxSelected>>", lambda e: self._schedule_plot())

    # ========== Color pickers ==========
    def _refresh_palette_combo(self):
        names = [p["name"] for p in self.palettes]
        self._palette_combo["values"] = names
        if self.current_palette_name in names:
            self._palette_combo.set(self.current_palette_name)
        elif names:
            self._palette_combo.set(names[0])

    def _refresh_color_pickers(self):
        """Rebuild the group-color UI rows in the config panel."""
        self._refresh_palette_combo()
        for w in self._color_inner.winfo_children():
            w.destroy()
        if not self.group_colors:
            ttk.Label(self._color_inner, text="（无分组）", foreground="#888").pack(anchor=tk.W)
            return
        for name, color in self.group_colors.items():
            row_frame = ttk.Frame(self._color_inner)
            row_frame.pack(fill=tk.X, pady=1)
            # color swatch button
            sw = tk.Label(row_frame, text="  ", bg=color, relief=tk.RAISED, width=4,
                          cursor="hand2")
            sw.pack(side=tk.LEFT, padx=(0, 6))
            sw.bind("<Button-1>", lambda e, n=name: self._on_color_pick(n))
            # group name
            ttk.Label(row_frame, text=name, font=("Segoe UI", 9)).pack(side=tk.LEFT)

    def _on_color_pick(self, group_name: str):
        from tkinter import colorchooser
        current = self.group_colors.get(group_name, "#000000")
        result = colorchooser.askcolor(color=current, title=f"选择{group_name}的颜色")
        if result and result[1]:
            self.group_colors[group_name] = result[1]
            self._refresh_color_pickers()
            self._auto_plot()

    # ========== Data ==========
    def load_csv(self):
        p = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"),
                                                   ("Excel files", "*.xlsx *.xls"),
                                                   ("All files", "*.*")])
        if not p:
            return
        try:
            if p.endswith((".xlsx", ".xls")):
                self.df = pd.read_excel(p, engine="openpyxl")
            else:
                self.df = pd.read_csv(p, encoding="utf-8-sig")
            self._on_data_loaded(f"已加载: {os.path.basename(p)}")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    def manual_input(self):
        w = tk.Toplevel(self.root)
        w.title("手动输入数据")
        w.geometry("500x400")
        w.transient(self.root)
        w.grab_set()

        ttk.Label(w, text="每行一组数据，用 Tab / 逗号 / 空格分隔\n"
                          "第一行为列名（X, Y, Group）", justify=tk.LEFT).pack(pady=6)

        txt = tk.Text(w, width=60, height=16, font=("Consolas", 10))
        txt.pack(padx=10, pady=4, fill=tk.BOTH, expand=True)
        txt.insert("1.0", "X\tY\tGroup\n1\t2.3\tA\n2\t4.1\tA\n3\t5.7\tB\n4\t8.2\tB\n5\t9.9\tC\n")

        def do_import():
            text = txt.get("1.0", tk.END).strip()
            if not text:
                return
            try:
                from io import StringIO
                # try tab first, then comma, then whitespace
                lines = [ln for ln in text.splitlines() if ln.strip()]
                sep = "\t" if "\t" in lines[0] else ("," if "," in lines[0] else None)
                self.df = pd.read_csv(StringIO(text), sep=sep or r"\s+", engine="python")
                self._on_data_loaded("手动输入已加载")
                w.destroy()
            except Exception as e:
                messagebox.showerror("解析失败", str(e))

        ttk.Button(w, text="确定", command=do_import, bootstyle="primary").pack(pady=6)

    def paste_from_clipboard(self):
        try:
            import win32clipboard as wc
            wc.OpenClipboard()
            data = wc.GetClipboardData()
            wc.CloseClipboard()
            from io import StringIO
            self.df = pd.read_csv(StringIO(data), sep="\t", engine="python")
            self._on_data_loaded("从剪贴板粘贴加载")
        except Exception as e:
            messagebox.showerror("粘贴失败", f"请先复制 Excel/CSV 数据到剪贴板\n{str(e)}")

    def _on_data_loaded(self, msg: str):
        self.group_colors = {}
        cols = list(self.df.columns)
        for cb in (self.col_x, self.col_y, self.col_g, self.col_a, self.col_b, self.col_c, self.col_g2):
            cb["values"] = cols
        if len(cols) >= 2:
            self.col_x.set(cols[0])
            self.col_y.set(cols[1])
        if len(cols) >= 3:
            self.col_g.set(cols[2])
            self.col_a.set(cols[0])
            self.col_b.set(cols[1])
            self.col_c.set(cols[2])
        else:
            self.col_g.set("")
        if len(cols) >= 4:
            self.col_g2.set(cols[3])
        self.status_var.set(f"✅ {msg} | {len(self.df)} 行, {len(cols)} 列")
        self._auto_plot()

    def _rebuild_axes(self, projection=None):
        """Replace self.ax with a fresh axes (regular or ternary)."""
        self.fig.clear()
        if projection == 'ternary':
            import mpltern
            self.ax = self.fig.add_subplot(111, projection='ternary')
        else:
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor("#ffffff")
            for spine in self.ax.spines.values():
                spine.set_color("#777777")
                spine.set_linewidth(0.6)
            self.ax.tick_params(labelsize=17, labelcolor="#000000", color="#777777",
                                direction="out", length=8, width=0.6)
            self.ax.grid(False)

    def _on_mode_switch(self):
        """Toggle between scatter and ternary mode."""
        if self.mode_var.get() == "ternary":
            self._scatter_cols_frame.grid_remove()
            self._ternary_cols_frame.grid()
            self._rebuild_axes('ternary')
        else:
            self._ternary_cols_frame.grid_remove()
            self._scatter_cols_frame.grid()
            self._rebuild_axes()
        self._auto_plot()

    # ========== Safe converters ==========
    @staticmethod
    def _safe_float(v, default=10.0):
        if v is None:
            return default
        v = str(v).strip()
        if not v:
            return default
        try:
            return float(v)
        except ValueError:
            return default

    @staticmethod
    def _nice_step(data_min, data_max):
        """Pick a 'nice' step size for tick marks from the data range."""
        rough = (data_max - data_min) / 5
        if rough <= 0:
            return 1
        magnitude = 10 ** np.floor(np.log10(rough))
        residual = rough / magnitude
        if residual < 1.5:
            return magnitude
        elif residual < 3.5:
            return 2 * magnitude
        elif residual < 7.5:
            return 5 * magnitude
        else:
            return 10 * magnitude

    @staticmethod
    def _safe_int(v, default=1):
        if v is None:
            return default
        v = str(v).strip()
        if not v:
            return default
        try:
            return int(v)
        except ValueError:
            return default

    @staticmethod
    def _safe_numeric(series):
        """Convert series to numeric, coerce errors to NaN, drop NaN."""
        s = pd.to_numeric(series, errors="coerce")
        return s.dropna()

    # ========== Palette management ==========
    _PALETTE_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  ".lunzi_palettes.json")

    _BUILTIN_PALETTES = [
        {"name": "默认蓝橙", "colors": [
            "#2864a0", "#dc7800", "#2ECC71", "#9B59B6", "#F39C12",
            "#1ABC9C", "#E74C3C", "#3498DB", "#E91E63", "#00BCD4",
            "#8BC34A", "#FF5722", "#673AB7", "#FF9800", "#795548"]},
        {"name": "柔和学术", "colors": [
            "#4477AA", "#AA7744", "#228833", "#BB5566", "#DDAA33",
            "#117777", "#885588", "#66CCEE", "#CC3311", "#999988",
            "#EE7733", "#33BBEE", "#EECC44", "#44AAAA", "#EE8866"]},
        {"name": "高对比", "colors": [
            "#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442",
            "#0072B2", "#D55E00", "#CC79A7", "#FF0000", "#00FF00",
            "#0000FF", "#FF00FF", "#00FFFF", "#800000", "#008000"]},
    ]

    def _load_palettes(self):
        try:
            with open(self._PALETTE_JSON, "r", encoding="utf-8") as f:
                import json
                self.palettes = json.load(f)
        except Exception:
            self.palettes = [dict(p) for p in self._BUILTIN_PALETTES]
        if not self.palettes:
            self.palettes = [dict(p) for p in self._BUILTIN_PALETTES]
        if not self.current_palette_name:
            self.current_palette_name = self.palettes[0]["name"]

    def _save_palettes(self):
        import json
        with open(self._PALETTE_JSON, "w", encoding="utf-8") as f:
            json.dump(self.palettes, f, ensure_ascii=False, indent=2)

    def _get_current_palette(self):
        for p in self.palettes:
            if p["name"] == self.current_palette_name:
                return p["colors"]
        return plt_cmap()

    def _on_palette_change(self, event=None):
        name = self._palette_combo.get()
        for p in self.palettes:
            if p["name"] == name:
                self.current_palette_name = name
                self.group_colors = {}
                self._auto_plot()
                return

    def _on_new_palette(self):
        if not self.group_colors:
            return
        w = tk.Toplevel(self.root)
        w.title("新建色板")
        w.geometry("300x120")
        w.transient(self.root)
        w.grab_set()
        ttk.Label(w, text="色板名称:").pack(pady=(12, 4))
        name_var = tk.StringVar(value="我的色板")
        e = ttk.Entry(w, textvariable=name_var, width=30)
        e.pack(padx=12)
        e.select_range(0, "end")
        e.focus_set()
        def do_save():
            name = name_var.get().strip()
            if name:
                colors = list(self.group_colors.values())
                self.palettes.append({"name": name, "colors": colors})
                self.current_palette_name = name
                self._save_palettes()
                self._refresh_palette_combo()
                w.destroy()
        ttk.Button(w, text="保存", command=do_save, bootstyle="success").pack(pady=(8, 8))

    def _on_delete_palette(self):
        if len(self.palettes) <= 1:
            return
        name = self.current_palette_name
        self.palettes = [p for p in self.palettes if p["name"] != name]
        self.current_palette_name = self.palettes[0]["name"]
        self._save_palettes()
        self._refresh_palette_combo()
        self.group_colors = {}
        self._auto_plot()

    def _on_import_palettes(self):
        p = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not p:
            return
        try:
            import json
            with open(p, "r", encoding="utf-8") as f:
                imported = json.load(f)
            if isinstance(imported, dict):
                imported = [imported]
            for item in imported:
                if isinstance(item, dict) and "name" in item and "colors" in item:
                    # avoid duplicate names
                    existing = [x for x in self.palettes if x["name"] == item["name"]]
                    if existing:
                        item["name"] = item["name"] + " (2)"
                    self.palettes.append(item)
            self._save_palettes()
            self._refresh_palette_combo()
        except Exception:
            pass

    # ========== Group colors ==========
    def _ensure_group_colors(self, group_names):
        """Sync group_colors dict. Keep manual edits, fill new groups from palette."""
        names = [str(n) for n in group_names]
        palette = self._get_current_palette()
        # drop stale entries
        stale = [k for k in self.group_colors if k not in names]
        for k in stale:
            del self.group_colors[k]
        # assign palette colors to new groups only
        for i, name in enumerate(names):
            if name not in self.group_colors:
                self.group_colors[name] = palette[i % len(palette)]

    # ========== Plot ==========
    _plot_job = None

    def _schedule_plot(self):
        if self.df is None:
            return
        if self._plot_job:
            self.root.after_cancel(self._plot_job)
        self._plot_job = self.root.after(300, self._auto_plot)

    def _auto_plot(self):
        if self.df is None:
            return
        try:
            if self.mode_var.get() == "ternary":
                self._do_ternary_plot()
            else:
                self._do_plot()
            if self.mode_var.get() != "ternary":
                self._refresh_color_pickers()
        except Exception as e:
            self.status_var.set(f"⚠️ 绘图出错: {e}")

    def _do_plot(self):
        # safe param reads
        fw = self._safe_float(self.fig_w.get(), 8)
        fh = self._safe_float(self.fig_h.get(), 5.5)
        ms = self._safe_float(self.marker_size.get(), 125)
        alpha = self._safe_float(self.alpha.get(), 1.0)
        order = self._safe_int(self.reg_order.get(), 1)

        self.fig.set_size_inches(fw, fh)
        self.ax.clear()

        x_col = self.col_x.get()
        y_col = self.col_y.get()
        g_col = self.col_g.get() or None

        if not x_col or not y_col or x_col not in self.df.columns or y_col not in self.df.columns:
            self.ax.set_title("请选择 X / Y 列")
            self.canvas.draw()
            return

        # convert data columns to numeric, drop invalid
        x_data = self._safe_numeric(self.df[x_col])
        y_data = self._safe_numeric(self.df[y_col])

        if x_data.empty or y_data.empty:
            self.ax.set_title("所选列没有有效的数值数据")
            self.canvas.draw()
            self.status_var.set("⚠️ 所选列无有效数值数据")
            return

        # align index for group merge
        valid_idx = x_data.index.intersection(y_data.index)
        xv = x_data.loc[valid_idx].values
        yv = y_data.loc[valid_idx].values
        n_plotted = len(xv)

        # point outline
        ec = '#555555' if self.show_outline.get() else 'face'
        lw = 0.5 if self.show_outline.get() else 0

        if g_col and g_col in self.df.columns:
            groups = self.df.loc[valid_idx].groupby(g_col, sort=False)
            group_names_list = [str(name) for name, _ in groups]
            self._ensure_group_colors(group_names_list)
            for name, grp in self.df.loc[valid_idx].groupby(g_col, sort=False):
                c = self.group_colors.get(str(name), plt_cmap()[0])
                gx = self._safe_numeric(grp[x_col]).values
                gy = self._safe_numeric(grp[y_col]).values
                # align individually
                g_min = min(len(gx), len(gy))
                self.ax.scatter(gx[:g_min], gy[:g_min], s=ms, alpha=alpha, c=[c],
                                label=str(name), edgecolors=ec, linewidths=lw, zorder=3)
            self.ax.legend(fontsize=8, framealpha=0.8, markerscale=0.7)
        else:
            self.ax.scatter(xv, yv, s=ms, alpha=alpha, c="#2864a0",
                            edgecolors=ec, linewidths=lw, zorder=3)

        # force ticks + axis limits (x from 0 since data are ratios)
        x_max = xv.max()
        y_min, y_max = yv.min(), yv.max()

        # manual x/y start override
        manual_x_str = self.xy_start_x.get().strip()
        manual_y_str = self.xy_start_y.get().strip()
        try:
            x_start = float(manual_x_str) if manual_x_str else None
        except ValueError:
            x_start = None
        try:
            y_start = float(manual_y_str) if manual_y_str else None
        except ValueError:
            y_start = None

        if x_start is not None:
            # Manual X start — force the lower bound to user's value
            x_start = max(x_start, 0)  # never below 0 for ratio data
            _set_ticks_from_min(self.ax.xaxis, x_start, x_max)
            self.ax.set_xlim(left=x_start)
        else:
            # Auto: start from 0, guard against negative
            _set_ticks_from_min(self.ax.xaxis, 0, x_max)
            xlo, _ = self.ax.get_xlim()
            if xlo < 0:
                self.ax.set_xlim(left=0)

        if y_start is not None:
            _set_ticks_from_min(self.ax.yaxis, y_start, y_max)
            self.ax.set_ylim(bottom=y_start)
        else:
            _set_ticks_from_min(self.ax.yaxis, y_min, y_max)

        # regression
        if self.show_reg.get() and len(xv) > 3:
            try:
                coeffs = np.polyfit(xv, yv, order)
                poly = np.poly1d(coeffs)
                x_smooth = np.linspace(xv.min(), xv.max(), 200)
                y_smooth = poly(x_smooth)
                self.ax.plot(x_smooth, y_smooth, color="#dc7800", linewidth=1.2,
                             linestyle="--", label=f"趋势线 (阶{order})", zorder=2)
                y_pred = poly(xv)
                ss_res = np.sum((yv - y_pred) ** 2)
                ss_tot = np.sum((yv - yv.mean()) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
                self.ax.text(0.97, 0.03, f"$R^2 = {r2:.3f}$",
                             transform=self.ax.transAxes, fontsize=9,
                             verticalalignment="bottom", horizontalalignment="right",
                             bbox=dict(boxstyle="round,pad=0.3", fc="wheat", alpha=0.7))
            except Exception:
                pass  # skip regression on error

        # labels (larger than tick labels which are 13)
        self.ax.set_xlabel(self.label_x.get() or x_col, fontsize=20, fontname="Arial")
        self.ax.set_ylabel(self.label_y.get() or y_col, fontsize=20, fontname="Arial")
        self.ax.set_title(self.title.get() or "", fontsize=16, fontweight="bold", fontname="Arial")

        # tick labels also Arial
        for label in self.ax.get_xticklabels() + self.ax.get_yticklabels():
            label.set_fontname("Arial")

        # style
        # white plot background, gray closed rectangle border
        self.ax.set_facecolor("#ffffff")
        for spine in self.ax.spines.values():
            spine.set_color("#777777")
            spine.set_linewidth(0.6)
        # ticks on left (y) and bottom (x)
        self.ax.tick_params(labelsize=17, labelcolor="#000000", color="#777777",
                            direction="out", length=8, width=0.6)
        # no grid
        self.ax.grid(False)

        self.fig.tight_layout()
        self.canvas.draw()
        self.status_var.set(f"✅ 已更新 | {n_plotted} 点")

    # ========== Ternary Plot ==========
    def _do_ternary_plot(self):
        """Ternary diagram via mpltern with zoom-to-data viewport."""
        a_col = self.col_a.get()
        b_col = self.col_b.get()
        c_col = self.col_c.get()
        g_col = self.col_g2.get() or None
        if not (a_col and b_col and c_col):
            self.ax.clear()
            self.ax.set_title("请选择 A/B/C 三列")
            self.canvas.draw()
            return

        ms = self._safe_float(self.marker_size.get(), 125)
        alpha = self._safe_float(self.alpha.get(), 1.0)

        # read data
        a_raw = self._safe_numeric(self.df[a_col])
        b_raw = self._safe_numeric(self.df[b_col])
        c_raw = self._safe_numeric(self.df[c_col])
        valid = a_raw.index.intersection(b_raw.index).intersection(c_raw.index)
        if len(valid) < 3:
            self.ax.clear()
            self.ax.set_title("有效数据不足 3 个点")
            self.canvas.draw()
            return

        A = a_raw.loc[valid].values
        B = b_raw.loc[valid].values
        C = c_raw.loc[valid].values
        pos = (A > 0) & (B > 0) & (C > 0)
        if pos.sum() < 3:
            self.ax.clear()
            self.ax.set_title("正值数据不足 3 个点")
            self.canvas.draw()
            return
        A, B, C = A[pos], B[pos], C[pos]

        self.ax.set_facecolor("#ffffff")

        # ternary coords: top=C, left=A, right=B
        S = A + B + C
        t, l, r = C/S, A/S, B/S

        # ---- 1. compute zoom bounds in original ternary space ----
        p = 0.08
        t_lo = max(0, t.min() - p)
        t_hi = min(1, t.max() + p)
        l_lo = max(0, l.min() - p)
        l_hi = min(1, l.max() + p)
        r_lo = max(0, r.min() - p)
        r_hi = min(1, r.max() + p)
        if t_hi - t_lo < 0.05:
            mid = (t_lo + t_hi) / 2
            t_lo = max(0, mid - 0.025)
            t_hi = min(1, mid + 0.025)
        if l_hi - l_lo < 0.05:
            mid = (l_lo + l_hi) / 2
            l_lo = max(0, mid - 0.025)
            l_hi = min(1, mid + 0.025)
        if r_hi - r_lo < 0.05:
            mid = (r_lo + r_hi) / 2
            r_lo = max(0, mid - 0.025)
            r_hi = min(1, mid + 0.025)

        D = 1 - t_lo - l_lo - r_lo  # zoom scale factor
        if D <= 0.01:
            # degenerate case — plot raw data in full triangle
            a_t, b_l, g_r = t, l, r
            t_lo = l_lo = r_lo = 0.0
            D = 1.0
        else:
            # affine transform: data-region triangle → full 0-1 triangle
            # Keeps triangle shape, spreads points across viewport
            a_t = (t - t_lo) / D  # transformed t (top axis)
            b_l = (l - l_lo) / D  # transformed l (left axis)
            g_r = (r - r_lo) / D  # transformed r (right axis)

        # No set_tlim/llim/rlim — full 0-1 triangle, shape preserved

        # ---- 2. tick step in original values ----
        step = 0.1
        max_span = max(t_hi - t_lo, l_hi - l_lo, r_hi - r_lo)
        if max_span < 0.2:
            step = 0.05
        elif max_span < 0.06:
            step = 0.02

        def _real_ticks(lo, hi, s):
            start = np.floor(lo / s) * s
            stop = np.ceil(hi / s) * s
            vals = np.arange(start, stop + s/2, s)
            vals = vals[(vals >= lo - 1e-10) & (vals <= hi + 1e-10)]
            return [round(v, 10) for v in vals]

        t_rv = _real_ticks(t_lo, t_lo + D, step)  # real values for t-edge (full zoom range)
        l_rv = _real_ticks(l_lo, l_lo + D, step)  # real values for l-edge (full zoom range)
        r_rv = _real_ticks(r_lo, r_lo + D, step)  # real values for r-edge (full zoom range)

        # convert to transformed positions (in full 0-1 triangle)
        t_tp = [(v - t_lo) / D for v in t_rv]
        l_tp = [(v - l_lo) / D for v in l_rv]
        r_tp = [(v - r_lo) / D for v in r_rv]

        # ---- 3. configure axes ----
        self.ax.set_tlabel(c_col)
        self.ax.set_llabel(a_col)
        self.ax.set_rlabel(b_col)
        for ax_name in ['t', 'l', 'r']:
            axis = getattr(self.ax, f'{ax_name}axis')
            axis.label.set_fontsize(17)
            axis.label.set_fontname('Arial')
            axis.label.set_fontweight('bold')
            axis.label.set_rotation(0)

        # Set ticks on all axes for grid lines
        self.ax.taxis.set_ticks(t_tp)
        self.ax.raxis.set_ticks(r_tp)
        self.ax.laxis.set_ticks(l_tp)

        # Hide all mpltern tick marks & labels (draw manually below)
        for axn in ['t', 'l', 'r']:
            ax = getattr(self.ax, f'{axn}axis')
            ax.set_ticklabels([])
            ax.set_tick_params(length=0, width=0)

        # no grid

        # spine color
        for spine in self.ax.spines.values():
            spine.set_color('#777777')
            spine.set_linewidth(0.8)

        # ---- 4. auto-scale marker size (in transformed coords) ----
        x_cart = g_r + 0.5 * a_t
        y_cart = np.sqrt(3)/2 * a_t
        data_span = max(x_cart.max() - x_cart.min(), y_cart.max() - y_cart.min(), 0.1)
        adjusted_ms = ms * min((0.5 / data_span) ** 0.7, 5.0)

        # ---- 5. plot data in transformed coords ----
        if g_col and g_col in self.df.columns:
            df_sub = self.df.loc[valid[pos]]
            for name, grp in df_sub.groupby(g_col, sort=False):
                ga = self._safe_numeric(grp[a_col]).values
                gb = self._safe_numeric(grp[b_col]).values
                gc = self._safe_numeric(grp[c_col]).values
                gs = ga + gb + gc
                if gs.min() <= 0:
                    continue
                gt0, gl0, gr0 = gc/gs, ga/gs, gb/gs
                ga_t = (gt0 - t_lo) / D
                gb_l = (gl0 - l_lo) / D
                gg_r = (gr0 - r_lo) / D
                ci = plt_cmap()[len(self.ax.collections) % len(plt_cmap())]
                self.ax.scatter(ga_t, gb_l, gg_r, s=adjusted_ms,
                                alpha=alpha, c=[ci], label=str(name),
                                edgecolors='face', linewidths=0, zorder=3)
            self.ax.legend(fontsize=9, framealpha=0.8, markerscale=0.7)
        else:
            self.ax.scatter(a_t, b_l, g_r, s=adjusted_ms, alpha=alpha,
                            c='#2864a0', edgecolors='face', linewidths=0, zorder=3)

        # ---- 6. manual ticks on left & right edges (horizontal labels) ----
        tick_pt = 10
        pad_pt = 5
        tk = dict(arrowstyle='-', color='#000000', lw=0.6)
        inv_s3 = 1 / np.sqrt(3)

        # Left edge (l-axis: A values) — data: x=-tp/√3, y=1-tp  tick: horizontal left
        for lv, tp_a in zip(l_rv, l_tp):
            xd = -inv_s3 * tp_a
            yd = 1 - tp_a
            self.ax.annotate('', xy=(xd, yd),
                             xytext=(-tick_pt, 0),
                             xycoords='data', textcoords='offset points',
                             annotation_clip=False,
                             arrowprops=tk)
            self.ax.annotate(f'{lv:g}', xy=(xd, yd),
                             xytext=(-(tick_pt+pad_pt), 0),
                             xycoords='data', textcoords='offset points',
                             annotation_clip=False,
                             ha='right', va='center', fontsize=13, fontname='Arial')

        # Right edge (t-values = C/Si) — data: x=tp/√3, y=1-tp, tp=1-t_tp  tick: horizontal right
        for tv, tp_t in zip(t_rv, t_tp):
            tp_r = 1 - tp_t
            xd = inv_s3 * tp_r
            yd = 1 - tp_r
            self.ax.annotate('', xy=(xd, yd),
                             xytext=(tick_pt, 0),
                             xycoords='data', textcoords='offset points',
                             annotation_clip=False,
                             arrowprops=tk)
            self.ax.annotate(f'{tv:g}', xy=(xd, yd),
                             xytext=((tick_pt+pad_pt), 0),
                             xycoords='data', textcoords='offset points',
                             annotation_clip=False,
                             ha='left', va='center', fontsize=13, fontname='Arial')

        self.fig.tight_layout()
        self.canvas.draw()
        self.status_var.set(f"✅ 三元图 {len(A)} 点 | 步长{step:.2f} | "
                           f"A[{l_rv[0]:.1f}-{l_rv[-1]:.1f}] "
                           f"B[{r_rv[0]:.1f}-{r_rv[-1]:.1f}] "
                           f"C[{t_rv[0]:.1f}-{t_rv[-1]:.1f}]")

    # ========== Export ==========
    def export(self, fmt: str):
        if self.df is None:
            messagebox.showinfo("提示", "请先加载数据")
            return
        p = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=[(f"{fmt.upper()} files", f"*.{fmt}")]
        )
        if not p:
            return
        try:
            if fmt == "svg":
                # use text elements (not paths) so CDR keeps text editable
                matplotlib.rcParams['svg.fonttype'] = 'none'
                # post-process for CDR compatibility
                buf = io.BytesIO()
                self.fig.savefig(buf, format="svg", bbox_inches=None,
                                 facecolor=self.fig.get_facecolor())
                clean = svg_for_cdr(buf.getvalue())
                with open(p, "wb") as f:
                    f.write(clean)
            else:
                self.fig.savefig(p, format=fmt, dpi=300 if fmt == "png" else None,
                                 bbox_inches=None, facecolor=self.fig.get_facecolor())
            self.status_var.set(f"📄 已导出: {os.path.basename(p)}")
            if messagebox.askyesno("导出成功", f"已保存到:\n{p}\n\n打开所在文件夹？"):
                os.startfile(os.path.dirname(p))
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def copy_to_clipboard(self):
        """Render figure to SVG bytes and put on clipboard."""
        if self.df is None:
            messagebox.showinfo("提示", "请先加载数据")
            return
        if not _HAS_WIN32:
            messagebox.showerror("不可用", "需要 pywin32，请运行: pip install pywin32")
            return

        svg = io.BytesIO()
        try:
            matplotlib.rcParams['svg.fonttype'] = 'none'
            self.fig.savefig(svg, format="svg", bbox_inches=None,
                             facecolor=self.fig.get_facecolor())
            svg_bytes = svg_for_cdr(svg.getvalue())
            ok = copy_svg_to_clipboard(svg_bytes)
            if ok:
                self.status_var.set("📋 SVG 已复制到剪贴板（无 PowerClip，可直接在 CDR 中编辑）")
            else:
                self.status_var.set("⚠️ 复制失败")
        except Exception as e:
            self.status_var.set(f"⚠️ 复制出错: {e}")

    # _paint_on_axes removed (unused after copy_to_clipboard refactor)

    # ========== Run ==========
    def run(self):
        self.root.mainloop()


# ========== Tick helpers ==========

def _set_ticks_from_min(axis, data_min, data_max):
    """Place ticks covering the full axis edge-to-edge (four corners all have ticks).

    Also extends the upper limit if data points would be clipped at the edge.
    """
    step = ScatterTool._nice_step(data_min, data_max)
    # Headroom to avoid clipping points at the edges
    lo_margin = step * 0.3  # 30% step padding at lower edge
    hi_margin = step * 0.3  # 30% step padding at upper edge
    first_tick = np.floor((data_min - lo_margin) / step) * step
    upper_limit = data_max + hi_margin
    last_tick = np.ceil(upper_limit / step) * step

    ticks = [round(t, 10) for t in np.arange(first_tick, last_tick + step * 0.5, step)]

    from matplotlib.ticker import FixedLocator
    axis.set_major_locator(FixedLocator(ticks))

    # snap axis limits exactly to first and last tick
    axis_name = axis.axis_name
    if axis_name == 'x':
        axis.axes.set_xlim(first_tick, last_tick)
    else:
        axis.axes.set_ylim(first_tick, last_tick)


# ========== SVG Post-processing for CorelDRAW ==========

def _attr(tag: str, name: str) -> str:
    """Extract attribute value from an XML tag string."""
    m = re.search(rf'\s{name}="([^"]*)"', tag)
    return m.group(1) if m else ""


def svg_for_cdr(svg_bytes: bytes) -> bytes:
    """Post-process matplotlib SVG for clean CDR import.

    - Removes clip-path attributes (causes PowerClip in CDR).
    - Expands <use> references to actual <path> elements
      (so points are independently editable, not linked symbols).
    """
    try:
        text = svg_bytes.decode("utf-8")

        # 1) Collect ALL named paths/shapes from ALL <defs> blocks
        defs_map = {}
        # There can be multiple <defs> blocks nested at different levels
        defs_blocks = re.finditer(r"<defs>(.*?)</defs>", text, re.DOTALL)
        for db in defs_blocks:
            content = db.group(1)
            # Extract id -> tag+attrs
            for m in re.finditer(
                r'<(\w+)\s+id="([^"]+)"\s+([^>]*?)/?\s*>', content, re.DOTALL
            ):
                tag, id_, attrs = m.groups()
                if id_ and tag != "style":
                    defs_map[id_] = f"<{tag} {attrs}/>"

        # 2) Remove all clip-path attributes
        text = re.sub(r'\s*clip-path="url\([^)]+\)"', "", text)

        # 3) Expand <use> elements
        def expand_use(m):
            tag = m.group(0)
            href = _attr(tag, "xlink:href") or _attr(tag, "href")
            if not (href and href.startswith("#")):
                return tag
            ref_id = href[1:]
            if ref_id not in defs_map:
                return tag
            ref_content = defs_map[ref_id]
            x = _attr(tag, "x")
            y = _attr(tag, "y")
            use_style = _attr(tag, "style")
            use_transform = _attr(tag, "transform")

            # Build translate from x,y
            if x and y:
                pos_tr = f'translate({x},{y})'
            elif x:
                pos_tr = f'translate({x},0)'
            elif y:
                pos_tr = f'translate(0,{y})'
            else:
                pos_tr = ""

            # Parse ref_content into components: opening tag, attrs, closing
            # We need to safely inject x/y as translate + merge transform + style
            tag_match = re.match(r'^<(\w+)\s+(.*?)(/?)>$', ref_content.strip(), re.DOTALL)
            if not tag_match:
                return tag
            inner_tag, attrs_raw, self_close = tag_match.groups()

            # Parse existing attributes
            existing = {}
            for a in re.finditer(r'(\w[-:\w]*)\s*=\s*"([^"]*)"', attrs_raw):
                existing[a.group(1)] = a.group(2)

            # Merge style
            if use_style and "style" in existing:
                # Append use style to existing style
                existing["style"] = existing["style"] + "; " + use_style
            elif use_style:
                existing["style"] = use_style

            # Merge transforms: pos_tr first, then use_transform, then existing transform
            transforms = []
            if pos_tr:
                transforms.append(pos_tr)
            if use_transform:
                transforms.append(use_transform)
            if "transform" in existing:
                transforms.append(existing["transform"])
            if transforms:
                existing["transform"] = " ".join(transforms)

            # Keep d attribute (always from defs)
            # Rebuild the element
            attr_parts = " ".join(f'{k}="{v}"' for k, v in existing.items() if k != "id")
            result = f"<{inner_tag} {attr_parts}/>"
            return result

        text = re.sub(r"<use\s[^>]*/>", expand_use, text)
        return text.encode("utf-8")
    except Exception:
        return svg_bytes


# color cycle
def plt_cmap():
    """Match 1.png style: blue & orange two-color scheme."""
    return ["#2864a0", "#dc7800", "#2ECC71", "#9B59B6", "#F39C12",
            "#1ABC9C", "#E74C3C", "#3498DB", "#E91E63", "#00BCD4",
            "#8BC34A", "#FF5722", "#673AB7", "#FF9800", "#795548"]


if __name__ == "__main__":
    ScatterTool().run()
