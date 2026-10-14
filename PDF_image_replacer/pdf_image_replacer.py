"""PDF Image Replacer - open a PDF, click an image area, paste/insert a new
image that is fitted to the original image's area, then Save / Save As."""

import io
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import fitz  # PyMuPDF
from PIL import Image, ImageGrab, ImageOps, ImageTk

APP_NAME = "PDF Image Replacer"
IMAGE_TYPES = [("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp"),
               ("All files", "*.*")]
FIT_MODES = ["Stretch to area", "Fit (keep aspect)", "Fill (crop to area)"]
MAX_UNDO = 30


class App(tk.Tk):
    def __init__(self, initial_file=None):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1200x850")
        self.minsize(700, 500)

        self.doc = None
        self.path = None
        self.dirty = False
        self.page_no = 0
        self.zoom = 1.0
        self.fit_width = True
        self.undo_stack = []
        self.images = []          # image infos on current page
        self.selection = None     # dict(rect, xref, transform)
        self.drag_start = None
        self.drag_item = None
        self._photo = None

        self._build_ui()
        self._bind_keys()
        self._update_state()
        if initial_file:
            self.after(100, lambda: self.open_file(initial_file))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        bar = ttk.Frame(self, padding=(6, 4))
        bar.pack(side=tk.TOP, fill=tk.X)

        def btn(text, cmd, width=None):
            b = ttk.Button(bar, text=text, command=cmd, width=width)
            b.pack(side=tk.LEFT, padx=2)
            return b

        def sep():
            ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        btn("Open...", self.open_dialog)
        self.btn_save = btn("Save", self.save)
        self.btn_save_as = btn("Save As...", self.save_as)
        sep()
        self.btn_prev = btn("◀", self.prev_page, 3)
        self.page_var = tk.StringVar()
        self.page_entry = ttk.Entry(bar, textvariable=self.page_var, width=5, justify=tk.CENTER)
        self.page_entry.pack(side=tk.LEFT)
        self.page_entry.bind("<Return>", self._goto_entry)
        self.page_total = ttk.Label(bar, text="/ 0")
        self.page_total.pack(side=tk.LEFT, padx=(2, 2))
        self.btn_next = btn("▶", self.next_page, 3)
        sep()
        btn("−", lambda: self.set_zoom(self.zoom / 1.2), 3)
        self.zoom_label = ttk.Label(bar, text="100%", width=6, anchor=tk.CENTER)
        self.zoom_label.pack(side=tk.LEFT)
        btn("+", lambda: self.set_zoom(self.zoom * 1.2), 3)
        btn("Fit Width", self.zoom_fit)
        sep()
        self.btn_paste = btn("Paste Image (Ctrl+V)", self.paste_clipboard)
        self.btn_insert = btn("Insert From File...", self.insert_from_file)
        self.btn_undo = btn("Undo", self.undo)
        sep()
        ttk.Label(bar, text="Mode:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value=FIT_MODES[0])
        ttk.Combobox(bar, textvariable=self.mode_var, values=FIT_MODES,
                     state="readonly", width=18).pack(side=tk.LEFT, padx=2)
        self.show_boxes = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Show image areas", variable=self.show_boxes,
                        command=self._draw_overlays).pack(side=tk.LEFT, padx=6)

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(body, bg="#5a5a5a", highlightthickness=0)
        vs = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.canvas.yview)
        hs = ttk.Scrollbar(body, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self.status = tk.StringVar(value="Open a PDF file to start (Ctrl+O).")
        ttk.Label(self, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W,
                  padding=(6, 2)).pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Configure>", self._on_resize)

        self.ctx_menu = tk.Menu(self, tearoff=0)
        self.ctx_menu.add_command(label="Paste Image Here (Ctrl+V)", command=self.paste_clipboard)
        self.ctx_menu.add_command(label="Insert Image From File...", command=self.insert_from_file)
        self.canvas.bind("<Button-3>", self._on_right_click)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _bind_keys(self):
        self.bind("<Control-o>", lambda e: self.open_dialog())
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<Control-Shift-S>", lambda e: self.save_as())
        self.bind("<Control-v>", self._key_paste)
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Next>", lambda e: self.next_page())
        self.bind("<Prior>", lambda e: self.prev_page())
        self.bind("<Escape>", lambda e: self._set_selection(None))

    def _key_paste(self, event):
        if event.widget is self.page_entry:
            return
        self.paste_clipboard()

    def _update_state(self):
        has = self.doc is not None
        st = tk.NORMAL if has else tk.DISABLED
        for b in (self.btn_save, self.btn_save_as, self.btn_prev, self.btn_next,
                  self.btn_paste, self.btn_insert):
            b.configure(state=st)
        self.btn_undo.configure(state=tk.NORMAL if self.undo_stack else tk.DISABLED)
        name = os.path.basename(self.path) if self.path else ""
        self.title(f"{'*' if self.dirty else ''}{name}{' - ' if name else ''}{APP_NAME}")
        if has:
            self.page_var.set(str(self.page_no + 1))
            self.page_total.configure(text=f"/ {self.doc.page_count}")
        self.zoom_label.configure(text=f"{round(self.zoom * 100)}%")

    # ------------------------------------------------------------ file ops
    def open_dialog(self):
        if not self._confirm_discard():
            return
        p = filedialog.askopenfilename(title="Open PDF",
                                       filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if p:
            self.open_file(p)

    def open_file(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open file:\n{e}")
            return
        if doc.needs_pass:
            while True:
                pw = simpledialog.askstring(APP_NAME, "This PDF is password protected.\nPassword:",
                                            show="*", parent=self)
                if pw is None:
                    return
                if doc.authenticate(pw):
                    break
        if self.doc:
            self.doc.close()
        self.doc = doc
        self.path = path
        self.dirty = False
        self.undo_stack.clear()
        self.page_no = 0
        self.fit_width = True
        self.selection = None
        self.render()
        self.status.set("Click an image (or drag a rectangle) to select an area, "
                        "then Paste (Ctrl+V) or Insert From File.")

    def _write(self, path):
        try:
            data = self.doc.tobytes(garbage=3, deflate=True)
            tmp = path + ".tmp~"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not save file:\n{e}")
            return False
        self.path = path
        self.dirty = False
        self._update_state()
        self.status.set(f"Saved: {path}")
        return True

    def save(self):
        if not self.doc:
            return False
        if not self.path:
            return self.save_as()
        return self._write(self.path)

    def save_as(self):
        if not self.doc:
            return False
        init = os.path.basename(self.path) if self.path else "document.pdf"
        root, ext = os.path.splitext(init)
        p = filedialog.asksaveasfilename(
            title="Save As", defaultextension=".pdf",
            initialdir=os.path.dirname(self.path) if self.path else None,
            initialfile=f"{root}_edited{ext or '.pdf'}",
            filetypes=[("PDF files", "*.pdf")])
        return self._write(p) if p else False

    def _confirm_discard(self):
        if not self.dirty:
            return True
        r = messagebox.askyesnocancel(APP_NAME, "Save changes to the current document?")
        if r is None:
            return False
        return self.save() if r else True

    def on_close(self):
        if self._confirm_discard():
            self.destroy()

    # ---------------------------------------------------------- rendering
    def _fit_zoom(self):
        page = self.doc[self.page_no]
        w = max(self.canvas.winfo_width() - 30, 100)
        return w / page.rect.width

    def render(self):
        if not self.doc:
            return
        page = self.doc[self.page_no]
        if self.fit_width:
            self.zoom = self._fit_zoom()
        pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.offset = (10, 10)
        self.canvas.create_rectangle(self.offset[0] + 3, self.offset[1] + 3,
                                     self.offset[0] + pix.width + 3, self.offset[1] + pix.height + 3,
                                     fill="#333", outline="")
        self.canvas.create_image(*self.offset, image=self._photo, anchor=tk.NW)
        self.canvas.configure(scrollregion=(0, 0, pix.width + 20, pix.height + 20))

        self.images = []
        try:
            for info in page.get_image_info(xrefs=True):
                r = fitz.Rect(info["bbox"]) & page.rect
                if r.is_empty or r.width < 2 or r.height < 2:
                    continue
                self.images.append({"rect": r, "xref": info.get("xref", 0),
                                    "transform": info.get("transform")})
        except Exception:
            pass
        if self.selection and self.selection.get("page") != self.page_no:
            self.selection = None
        self._draw_overlays()
        self._update_state()

    def _to_canvas(self, rect):
        ox, oy = self.offset
        z = self.zoom
        return (ox + rect.x0 * z, oy + rect.y0 * z, ox + rect.x1 * z, oy + rect.y1 * z)

    def _to_pdf(self, cx, cy):
        ox, oy = self.offset
        return fitz.Point((cx - ox) / self.zoom, (cy - oy) / self.zoom)

    def _draw_overlays(self):
        self.canvas.delete("overlay")
        if not self.doc:
            return
        if self.show_boxes.get():
            for im in self.images:
                self.canvas.create_rectangle(*self._to_canvas(im["rect"]), outline="#1e90ff",
                                             dash=(4, 3), width=1, tags="overlay")
        if self.selection:
            self.canvas.create_rectangle(*self._to_canvas(self.selection["rect"]),
                                         outline="#ff2020", width=3, tags="overlay")

    def _on_resize(self, _e):
        if self.doc and self.fit_width:
            if getattr(self, "_resize_job", None):
                self.after_cancel(self._resize_job)
            self._resize_job = self.after(150, self.render)

    # --------------------------------------------------------- navigation
    def goto(self, n):
        if not self.doc:
            return
        n = max(0, min(self.doc.page_count - 1, n))
        if n != self.page_no:
            self.page_no = n
            self.selection = None
            self.render()
            self.canvas.yview_moveto(0)

    def next_page(self):
        self.goto(self.page_no + 1)

    def prev_page(self):
        self.goto(self.page_no - 1)

    def _goto_entry(self, _e):
        try:
            self.goto(int(self.page_var.get()) - 1)
        except ValueError:
            self._update_state()
        self.canvas.focus_set()

    def set_zoom(self, z):
        if not self.doc:
            return
        self.fit_width = False
        self.zoom = max(0.1, min(8.0, z))
        self.render()

    def zoom_fit(self):
        self.fit_width = True
        self.render()

    def _on_wheel(self, e):
        if e.state & 0x0004:  # Ctrl
            self.set_zoom(self.zoom * (1.1 if e.delta > 0 else 1 / 1.1))
        elif e.state & 0x0001:  # Shift
            self.canvas.xview_scroll(-1 if e.delta > 0 else 1, "units")
        else:
            top, bottom = self.canvas.yview()
            if e.delta < 0 and bottom >= 1.0:
                if self.doc and self.page_no < self.doc.page_count - 1:
                    self.next_page()
                return
            if e.delta > 0 and top <= 0.0:
                if self.doc and self.page_no > 0:
                    self.prev_page()
                    self.canvas.yview_moveto(1.0)
                return
            self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    # ---------------------------------------------------------- selection
    def _image_at(self, pt):
        hits = [im for im in self.images if pt in im["rect"]]
        return min(hits, key=lambda im: im["rect"].width * im["rect"].height) if hits else None

    def _set_selection(self, sel):
        self.selection = sel
        self._draw_overlays()
        if sel:
            r = sel["rect"]
            kind = "Image" if sel.get("xref") is not None else "Custom area"
            self.status.set(f"{kind} selected on page {self.page_no + 1}: "
                            f"{r.width:.0f} x {r.height:.0f} pt.  Now press Ctrl+V or "
                            f"use 'Insert From File...'.")
        elif self.doc:
            self.status.set("Selection cleared.")

    def _on_motion(self, e):
        if not self.doc:
            return
        pt = self._to_pdf(self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))
        self.canvas.configure(cursor="hand2" if self._image_at(pt) else "crosshair")

    def _on_press(self, e):
        self.canvas.focus_set()
        if not self.doc:
            return
        self.drag_start = (self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))
        self.drag_item = None

    def _on_drag(self, e):
        if not self.drag_start:
            return
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        x0, y0 = self.drag_start
        if self.drag_item is None and abs(x - x0) + abs(y - y0) > 6:
            self.drag_item = self.canvas.create_rectangle(x0, y0, x, y, outline="#ff8c00",
                                                          dash=(5, 3), width=2)
        if self.drag_item:
            self.canvas.coords(self.drag_item, x0, y0, x, y)

    def _on_release(self, e):
        if not self.drag_start:
            return
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        x0, y0 = self.drag_start
        self.drag_start = None
        page_rect = self.doc[self.page_no].rect
        if self.drag_item:
            self.canvas.delete(self.drag_item)
            self.drag_item = None
            r = fitz.Rect(self._to_pdf(min(x0, x), min(y0, y)),
                          self._to_pdf(max(x0, x), max(y0, y))) & page_rect
            if r.width > 3 and r.height > 3:
                self._set_selection({"rect": r, "xref": None, "transform": None,
                                     "page": self.page_no})
            return
        im = self._image_at(self._to_pdf(x, y))
        if im:
            self._set_selection(dict(im, page=self.page_no))
        else:
            self._set_selection(None)
            self.status.set("No image here. Click an image (blue dashed box) "
                            "or drag to select a custom area.")

    def _on_right_click(self, e):
        if not self.doc:
            return
        pt = self._to_pdf(self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))
        if not (self.selection and pt in self.selection["rect"]):
            im = self._image_at(pt)
            if im:
                self._set_selection(dict(im, page=self.page_no))
        self.ctx_menu.tk_popup(e.x_root, e.y_root)

    # ------------------------------------------------------ image sources
    def paste_clipboard(self):
        if not self._check_selection():
            return
        try:
            data = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not read clipboard:\n{e}")
            return
        img = None
        if isinstance(data, Image.Image):
            img = data
        elif isinstance(data, list):
            for p in data:
                try:
                    img = Image.open(p)
                    img.load()
                    break
                except Exception:
                    continue
        if img is None:
            messagebox.showinfo(APP_NAME, "The clipboard does not contain an image.\n"
                                          "Copy an image (or an image file) first.")
            return
        self.apply_image(img)

    def insert_from_file(self):
        if not self._check_selection():
            return
        p = filedialog.askopenfilename(title="Choose Image", filetypes=IMAGE_TYPES)
        if not p:
            return
        try:
            img = Image.open(p)
            img.load()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open image:\n{e}")
            return
        self.apply_image(img)

    def _check_selection(self):
        if not self.doc:
            return False
        if not self.selection:
            messagebox.showinfo(APP_NAME, "First click an image in the PDF (or drag a rectangle) "
                                          "to select the target area.")
            return False
        return True

    # ------------------------------------------------------- core editing
    def _prepare_image(self, img, target_w, target_h):
        """Return encoded image bytes shaped to the target aspect ratio."""
        img = ImageOps.exif_transpose(img)
        has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
        img = img.convert("RGBA" if has_alpha else "RGB")
        mode = self.mode_var.get()
        aspect = target_w / target_h if target_h else 1
        w, h = img.size
        if mode == FIT_MODES[1]:  # fit: pad with transparency
            if abs(w / h - aspect) > 0.01:
                nw, nh = (w, round(w / aspect)) if w / h > aspect else (round(h * aspect), h)
                canvas = Image.new("RGBA", (max(nw, 1), max(nh, 1)), (255, 255, 255, 0))
                canvas.paste(img, ((nw - w) // 2, (nh - h) // 2))
                img, has_alpha = canvas, True
        elif mode == FIT_MODES[2]:  # fill: crop center
            if abs(w / h - aspect) > 0.01:
                img = ImageOps.fit(img, (w, max(round(w / aspect), 1)) if w / h < aspect
                                   else (max(round(h * aspect), 1), h), Image.LANCZOS)
        # avoid absurdly large embedded images (max ~3x of 300 dpi-ish)
        max_side = 4000
        if max(img.size) > max_side:
            s = max_side / max(img.size)
            img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))),
                             Image.LANCZOS)
        buf = io.BytesIO()
        if has_alpha:
            img.save(buf, "PNG", optimize=True)
        else:
            img.save(buf, "JPEG", quality=92)
        return buf.getvalue()

    def _xref_usage(self, xref):
        count = 0
        for p in self.doc:
            for info in p.get_image_info(xrefs=True):
                if info.get("xref") == xref:
                    count += 1
                    if count > 1:
                        return count
        return count

    def apply_image(self, img):
        sel = self.selection
        page = self.doc[self.page_no]
        rect = sel["rect"]
        xref = sel.get("xref")
        tf = sel.get("transform")
        if tf and xref:
            tw, th = math.hypot(tf[0], tf[1]), math.hypot(tf[2], tf[3])
        else:
            tw, th = rect.width, rect.height
        try:
            data = self._prepare_image(img, tw, th)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not process image:\n{e}")
            return

        snapshot = self.doc.tobytes()
        try:
            if xref and self._xref_usage(xref) == 1:
                # replace the image object itself: same position, size and rotation
                page.replace_image(xref, stream=data)
                how = "replaced"
            else:
                # shared / inline image or custom area: cover it and place new image on top
                page.draw_rect(rect, color=None, fill=(1, 1, 1), overlay=True)
                page.insert_image(rect, stream=data, keep_proportion=False, overlay=True)
                how = "placed"
        except Exception as e:
            self.doc = fitz.open(stream=snapshot, filetype="pdf")
            messagebox.showerror(APP_NAME, f"Could not insert image:\n{e}")
            self.render()
            return

        self.undo_stack.append((snapshot, self.page_no))
        del self.undo_stack[:-MAX_UNDO]
        self.dirty = True
        self.render()
        # keep a selection on the new image so it can be replaced again
        self.selection = None
        for im in self.images:
            if abs(im["rect"].x0 - rect.x0) < 1 and abs(im["rect"].y0 - rect.y0) < 1 \
                    and abs(im["rect"].x1 - rect.x1) < 1 and abs(im["rect"].y1 - rect.y1) < 1:
                self.selection = dict(im, page=self.page_no)
        self._draw_overlays()
        self.status.set(f"Image {how} ({rect.width:.0f} x {rect.height:.0f} pt). "
                        f"Use Save (Ctrl+S) or Save As to write the PDF.")

    def undo(self):
        if not self.undo_stack:
            return
        data, page_no = self.undo_stack.pop()
        self.doc.close()
        self.doc = fitz.open(stream=data, filetype="pdf")
        self.page_no = min(page_no, self.doc.page_count - 1)
        self.selection = None
        self.dirty = bool(self.undo_stack) or self.dirty
        self.render()
        self.status.set("Undone.")


def main():
    initial = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(initial).mainloop()


if __name__ == "__main__":
    main()
