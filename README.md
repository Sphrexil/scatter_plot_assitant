<h1>
  Scatter Plot Tool &nbsp;/&nbsp; 散点图工具
</h1>

<br>

<details open>
<summary><b>English</b> (click for 中文)</summary>

<br>

A Python/Tkinter scatter plot tool with ternary diagram support. Export vector graphics directly to CorelDRAW.

## Features

- **Scatter plot** — X/Y axes with optional grouping, trend lines, and point outlines
- **Ternary plot** — Triangular A/B/C component diagram via mpltern with custom ticks and CDR-ready SVG
- **Group colors** — Auto-assign from palettes, manual per-group picking, import/export palettes
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
3. The plot auto-zooms to the data region with custom ticks on left and right edges

### Group Colors

- Groups are auto-assigned colors from the selected palette
- Click a color swatch to pick a custom color
- Switch palettes from the dropdown
- Create new palettes, delete, or import from JSON files

### Export

- Save as SVG, PDF, or PNG
- **Copy SVG to Clipboard** — Paste directly into CorelDRAW (text stays editable, no PowerClip)

## Data Format

CSV with a header row. Example:

| X | Y | Group |
|---|---|-------|
| 1 | 2.3 | A |
| 2 | 4.1 | A |
| 3 | 5.7 | B |

## License

MIT

</details>

<details>
<summary><b>中文</b> (点击展开)</summary>

<br>

Python/Tkinter 散点图工具，支持三元图，可直接导出矢量图到 CorelDRAW。

## 功能

- **散点图** — X/Y 轴，支持分组着色、趋势线、散点轮廓线
- **三元图** — A/B/C 三组分三角图（基于 mpltern），自定义刻度，SVG 可直接导入 CDR
- **分组颜色** — 内置色板自动配色，手动修改每组颜色，色板导入/导出
- **导出** — SVG（CDR 兼容，无 PowerClip）、PDF、PNG
- **剪贴板** — 一键复制 SVG 到剪贴板，直接粘贴到 CorelDRAW 中编辑

## 环境要求

```bash
pip install matplotlib pandas numpy pywin32 mpltern
```

## 使用方法

### 启动

```bash
python scatter_tool.py
```

或在 Windows 上双击 `start.bat`。

### 加载数据

- **打开 CSV** — 加载 `.csv` / `.xlsx` 文件
- **手动输入** — 在内置编辑器中粘贴或输入数据
- **从剪贴板粘贴** — 从 Excel 复制后一键粘贴

### 散点图

1. 选择 X / Y 列，可选分组列
2. 调整标记大小、透明度
3. 勾选趋势线、散点轮廓线
4. 点击**更新绘图**

### 三元图

1. 切换到三元图模式
2. 选择 A / B / C 三组分列，可选分组列
3. 自动缩放到数据区域，左右边缘显示自定义刻度

### 分组颜色

- 根据所选色板自动为各组分配颜色
- 点击颜色方块可手动修改颜色
- 下拉切换色板
- 新建色板、删除、从 JSON 文件导入

### 导出

- 保存为 SVG / PDF / PNG
- **复制 SVG 到剪贴板** — 直接粘贴到 CorelDRAW（文字保持可编辑，无 PowerClip 裁剪问题）

## 数据格式

CSV 文件首行为列名。示例：

| X | Y | Group |
|---|---|-------|
| 1 | 2.3 | A |
| 2 | 4.1 | A |
| 3 | 5.7 | B |

## 许可证

MIT

</details>
