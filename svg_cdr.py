"""SVG post-processing helpers for cleaner CorelDRAW import."""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET


def _svg_length_to_points(value: str) -> float | None:
    match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*", value or "")
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2).lower() or "pt"
    if unit == "pt":
        return number
    if unit == "in":
        return number * 72
    if unit == "mm":
        return number * 72 / 25.4
    if unit == "cm":
        return number * 72 / 2.54
    if unit == "px":
        return number * 72 / 96
    return None


def _format_mm(points: float) -> str:
    return f"{points * 25.4 / 72:.4f}mm"


def _normalize_root_size(root: ET.Element) -> None:
    """Write explicit millimeter dimensions while keeping the original viewBox."""
    width_pt = _svg_length_to_points(root.attrib.get("width", ""))
    height_pt = _svg_length_to_points(root.attrib.get("height", ""))
    if (width_pt is None or height_pt is None) and root.attrib.get("viewBox"):
        parts = root.attrib["viewBox"].replace(",", " ").split()
        if len(parts) == 4:
            try:
                width_pt = width_pt if width_pt is not None else float(parts[2])
                height_pt = height_pt if height_pt is not None else float(parts[3])
            except ValueError:
                return
    if width_pt is not None and height_pt is not None:
        root.attrib["width"] = _format_mm(width_pt)
        root.attrib["height"] = _format_mm(height_pt)


def svg_for_cdr(svg_bytes: bytes) -> bytes:
    """Post-process matplotlib SVG for clean CDR import.

    - Removes clip-path attributes (causes PowerClip in CDR).
    - Expands <use> references to actual elements so markers are independently editable.
    """
    try:
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
        root = ET.fromstring(svg_bytes)
        _normalize_root_size(root)

        defs_map = {
            elem.attrib["id"]: elem
            for elem in root.iter()
            if "id" in elem.attrib and not elem.tag.endswith("style")
        }

        for elem in root.iter():
            for key in list(elem.attrib):
                if key.endswith("clip-path"):
                    del elem.attrib[key]

        xlink_href = "{http://www.w3.org/1999/xlink}href"

        def local_name(tag: str) -> str:
            return tag.rsplit("}", 1)[-1]

        def expand_uses(parent: ET.Element) -> None:
            children = list(parent)
            for index, child in enumerate(children):
                if local_name(child.tag) == "use":
                    href = child.attrib.get(xlink_href) or child.attrib.get("href")
                    ref = defs_map.get(href[1:]) if href and href.startswith("#") else None
                    if ref is None:
                        continue
                    replacement = copy.deepcopy(ref)
                    replacement.attrib.pop("id", None)

                    use_style = child.attrib.get("style", "")
                    ref_style = replacement.attrib.get("style", "")
                    if use_style:
                        replacement.attrib["style"] = (
                            f"{ref_style}; {use_style}" if ref_style else use_style
                        )

                    transforms = []
                    x = child.attrib.get("x")
                    y = child.attrib.get("y")
                    if x and y:
                        transforms.append(f"translate({x},{y})")
                    elif x:
                        transforms.append(f"translate({x},0)")
                    elif y:
                        transforms.append(f"translate(0,{y})")
                    if child.attrib.get("transform"):
                        transforms.append(child.attrib["transform"])
                    if replacement.attrib.get("transform"):
                        transforms.append(replacement.attrib["transform"])
                    if transforms:
                        replacement.attrib["transform"] = " ".join(transforms)
                    replacement.tail = child.tail
                    parent[index] = replacement
                else:
                    expand_uses(child)

        expand_uses(root)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    except Exception:
        return svg_bytes
