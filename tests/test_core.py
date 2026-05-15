import io
import unittest

import pandas as pd
from PIL import Image

from scatter_tool import _png_to_dib
from plot_data import prepare_ternary_data, prepare_xy_data
from svg_cdr import svg_for_cdr


class CoreHelpersTest(unittest.TestCase):
    def test_prepare_xy_data_keeps_x_y_aligned_after_numeric_drop(self):
        df = pd.DataFrame({
            "x": [1, "bad", 3],
            "y": [10, 20, "bad"],
            "group": ["A", "B", "C"],
        })

        result = prepare_xy_data(df, "x", "y", "group")

        self.assertEqual(result["_x"].tolist(), [1.0])
        self.assertEqual(result["_y"].tolist(), [10.0])
        self.assertEqual(result["_group"].tolist(), ["A"])

    def test_prepare_ternary_data_keeps_only_aligned_positive_rows(self):
        df = pd.DataFrame({
            "a": [1, 0, 3, "bad"],
            "b": [1, 2, -1, 4],
            "c": [1, 3, 3, 4],
            "group": ["A", "B", "C", "D"],
        })

        result = prepare_ternary_data(df, "a", "b", "c", "group")

        self.assertEqual(result["_a"].tolist(), [1.0])
        self.assertEqual(result["_b"].tolist(), [1])
        self.assertEqual(result["_c"].tolist(), [1])
        self.assertEqual(result["_group"].tolist(), ["A"])

    def test_svg_for_cdr_removes_clip_paths_and_expands_use_elements(self):
        svg = b'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
          <defs><path id="marker" d="M0 0L1 1" style="fill:#000"/></defs>
          <g clip-path="url(#clip)"><use xlink:href="#marker" x="5" y="6" style="stroke:#fff"/></g>
        </svg>'''

        result = svg_for_cdr(svg).decode("utf-8")

        self.assertNotIn("clip-path", result)
        self.assertNotIn("<use", result)
        self.assertIn("translate(5,6)", result)
        self.assertIn("stroke:#fff", result)

    def test_svg_for_cdr_normalizes_point_size_to_millimeters(self):
        svg = b'''<svg xmlns="http://www.w3.org/2000/svg" width="576pt" height="446.4pt" viewBox="0 0 576 446.4">
          <path d="M0 0L1 1"/>
        </svg>'''

        result = svg_for_cdr(svg).decode("utf-8")

        self.assertIn('width="203.2000mm"', result)
        self.assertIn('height="157.4800mm"', result)
        self.assertIn('viewBox="0 0 576 446.4"', result)

    def test_png_to_dib_builds_a_valid_top_down_32bit_dib(self):
        img = Image.new("RGBA", (2, 1), (255, 0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        dib = _png_to_dib(buf.getvalue())

        self.assertGreater(len(dib), 40)
        header_size = int.from_bytes(dib[0:4], "little")
        width = int.from_bytes(dib[4:8], "little", signed=True)
        height = int.from_bytes(dib[8:12], "little", signed=True)
        bit_count = int.from_bytes(dib[14:16], "little")
        self.assertEqual(header_size, 40)
        self.assertEqual(width, 2)
        self.assertEqual(height, -1)
        self.assertEqual(bit_count, 32)


if __name__ == "__main__":
    unittest.main()
