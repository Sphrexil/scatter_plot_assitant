# Scatter Plot Tool

A Python/Tkinter scatter plot tool with ternary diagram support. Export vector graphics directly to CorelDRAW.

## Features

- **Scatter plot** — X/Y axes with optional grouping, trend lines, and point outlines
- **Ternary plot** — Triangular A/B/C component diagram via mpltern, with custom tick marks and CDR-ready SVG output
- **Group colors** — Auto-assign colors from built-in palettes, manually pick per-group colors, import/export color palettes
- **Export** — SVG (CorelDRAW-compatible, no PowerClip), PDF, PNG
- **Clipboard** — Copy SVG directly to clipboard for paste into CorelDRAW

## Requirements

```bash
pip install matplotlib pandas numpy pywin32 mpltern
```

## Usage

### Quick Start

```bash
python scatter_tool.py
```

Or double-click `start.bat` on Windows.

### Load Data

- **Open CSV** — Load from `.csv` / `.xlsx` files
- **Manual Input** — Paste or type data in the built-in editor
- **Paste from Clipboard** — Paste tab-separated data from Excel

### Scatter Plot

1. Select X / Y columns and an optional group column
2. Adjust marker size, transparency
3. Toggle trend line and point outlines
4. Click **Update Plot**

### Ternary Plot

1. Switch to ternary mode
2. Select A / B / C component columns and an optional group column
3. The plot automatically zooms to the data region with custom tick marks on left and right edges

### Group Colors

- Groups are auto-assigned colors from the selected palette
- Click a color swatch to pick a custom color
- Switch palettes from the dropdown
- Create new palettes, delete, or import from JSON files

### Export

- Save as SVG, PDF, or PNG
- **Copy SVG to Clipboard** — Paste directly into CorelDRAW (text remains editable, no PowerClip clipping)

## Data Format

CSV with a header row. Example:

| X | Y | Group |
|---|---|-------|
| 1 | 2.3 | A |
| 2 | 4.1 | A |
| 3 | 5.7 | B |

## License

MIT
