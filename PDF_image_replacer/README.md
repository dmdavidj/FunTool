# PDF Image Replacer

A portable Windows tool for replacing images inside a PDF. Open a PDF, click an image, then paste or pick a new image. The new image is placed in the original image's exact position and size. Save the result over the original file or as a new file.

No installation is required. Just run `PDFImageReplacer.exe`.

## Features

- View PDF pages with zoom and page navigation
- Images on each page are outlined with a blue dashed box so you can find them
- Replace an image by clicking it and then:
  - pasting from the clipboard (Ctrl+V), or
  - choosing an image file
- Drag a rectangle to place an image in any area, even one with no image
- Three fit modes: stretch, keep aspect ratio, or crop to fill
- Undo (up to 30 steps)
- Save (overwrite) or Save As (new file)
- Opens password-protected PDFs

## Getting Started

1. Copy `PDFImageReplacer.exe` anywhere, such as the desktop or a USB drive.
2. Double-click it to run.
   - You can also drag a PDF file onto the exe to open it right away.

> The first launch may take a few seconds while the program unpacks itself.

## How to Use

### 1. Open a PDF
Click **Open...** or press **Ctrl+O**. The first page is shown, and every image on the page is outlined with a blue dashed box.

### 2. Select the target area
- **Click an image** to select it. The selection is outlined in red.
- **Drag a rectangle** to select any area, including areas with no image.
- Press **Esc** to clear the selection.

### 3. Insert the new image
- **Paste Image (Ctrl+V)** uses the image on the clipboard, such as a screenshot or an image copied from a browser or image editor. If you copied an image *file* in File Explorer, that works too.
- **Insert From File...** lets you choose an image file (PNG, JPG, BMP, GIF, TIFF or WEBP).
- You can also **right-click** the selected image for the same options.

The new image fills the selected area according to the **Mode** setting:

| Mode | Behavior |
|---|---|
| **Stretch to area** (default) | Stretches the image to exactly fill the area |
| **Fit (keep aspect)** | Keeps the image's proportions; leftover space is transparent |
| **Fill (crop to area)** | Keeps proportions and fills the area; trims the edges that don't fit |

### 4. Save
- **Save** (**Ctrl+S**) overwrites the opened file.
- **Save As...** (**Ctrl+Shift+S**) saves to a new file. The default name is `<original>_edited.pdf`.

If you close the program with unsaved changes, it asks whether to save.

## Keyboard and Mouse Shortcuts

| Action | Shortcut |
|---|---|
| Open PDF | Ctrl+O |
| Save | Ctrl+S |
| Save As | Ctrl+Shift+S |
| Paste image into selection | Ctrl+V |
| Undo | Ctrl+Z |
| Next / previous page | Page Down / Page Up, or scroll past the page edge |
| Zoom in / out | Ctrl + mouse wheel, or the **+** / **−** buttons |
| Fit page to window width | **Fit Width** button |
| Scroll horizontally | Shift + mouse wheel |
| Clear selection | Esc |

## How Replacement Works

- **An image used only once in the document:** the image object itself is replaced. The new image keeps the original's exact position, size and rotation. The old image data is removed when you save.
- **An image shared with other pages, an inline image, or a dragged area:** the area is covered with white and the new image is placed on top. Other pages that use the same image are not changed.

Large images are scaled down to at most 4000 px on the longest side to keep the file size reasonable. Images with transparency are stored as PNG; other images are stored as JPEG (quality 92).

## Limitations

- Only raster images are detected as clickable images. Charts or drawings made of vector graphics are not outlined. Use drag selection to place an image over them.
- When the program covers an area instead of replacing the image, the original image is still in the file underneath the new one.
- Pages with unusual rotation settings may place dragged-area images less accurately.

## Building From Source

Requirements: Python 3.10+ on Windows.

```bash
python -m venv venv
venv\Scripts\pip install pymupdf pillow pyinstaller

# Run directly
venv\Scripts\python pdf_image_replacer.py

# Build the portable single-file exe (output: dist\PDFImageReplacer.exe)
venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name PDFImageReplacer pdf_image_replacer.py
```

### Project Files

| File | Description |
|---|---|
| `pdf_image_replacer.py` | Full application source (Tkinter GUI + PyMuPDF) |
| `dist/PDFImageReplacer.exe` | Built portable executable |
| `README.md` | This document |

## Libraries Used

- [PyMuPDF](https://pymupdf.readthedocs.io/) for PDF rendering and editing (AGPL-3.0)
- [Pillow](https://python-pillow.org/) for image processing and clipboard access
- Tkinter for the GUI (included with Python)
- [PyInstaller](https://pyinstaller.org/) for packaging the exe
