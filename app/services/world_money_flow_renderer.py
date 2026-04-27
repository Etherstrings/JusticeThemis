# -*- coding: utf-8 -*-
"""Static PNG renderer for the "昨天世界钱往哪里" image payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CANVAS_SIZE = (1242, 4600)
MIN_CANVAS_HEIGHT = 2208
MARGIN_X = 64
SECTION_GAP = 26


PALETTE = {
    "bg": "#f6f1e8",
    "ink": "#171717",
    "muted": "#63615d",
    "hairline": "#d8d0c2",
    "red": "#b23a2f",
    "green": "#287553",
    "blue": "#285c8f",
    "gold": "#a86f1a",
    "panel": "#fffaf1",
    "soft_blue": "#eaf1f7",
    "soft_red": "#f7e7e3",
    "soft_green": "#e7f2ec",
    "soft_gold": "#f5ecd8",
}


FONT_CANDIDATES = (
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
)


def render_world_money_flow_png(payload: dict[str, Any], output_path: str | Path) -> Path:
    renderer = _WorldMoneyFlowRenderer(payload=payload)
    return renderer.render(output_path)


class _WorldMoneyFlowRenderer:
    def __init__(self, *, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.image = Image.new("RGB", CANVAS_SIZE, PALETTE["bg"])
        self.draw = ImageDraw.Draw(self.image)
        self.font_path = self._resolve_font_path()
        self.fonts = {
            "title": self._font(58),
            "subtitle": self._font(28),
            "section": self._font(34),
            "item_title": self._font(25),
            "body": self._font(22),
            "small": self._font(19),
            "badge": self._font(21),
            "number": self._font(23),
        }

    def render(self, output_path: str | Path) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        y = 52
        y = self._render_title_block(y)
        y = self._render_flow_block(y)
        y = self._render_drivers_block(y)
        y = self._render_data_block(y)
        y = self._render_mapping_block(y)
        bottom = self._render_footer(y + 18)
        crop_height = min(CANVAS_SIZE[1], max(MIN_CANVAS_HEIGHT, bottom + 28))
        self.image = self.image.crop((0, 0, CANVAS_SIZE[0], crop_height))

        self.image.save(output)
        return output

    def _render_title_block(self, y: int) -> int:
        blocks = dict(self.payload.get("image_blocks", {}) or {})
        title_block = dict(blocks.get("title_block", {}) or {})
        title = str(title_block.get("title", "")).strip() or "昨天世界钱往哪里"
        date = str(title_block.get("date", "")).strip()
        conclusion = str(title_block.get("conclusion", "")).strip()
        summary = str(title_block.get("summary", "")).strip()

        self.draw.text((MARGIN_X, y), title, font=self.fonts["title"], fill=PALETTE["ink"])
        self._draw_pill(CANVAS_SIZE[0] - MARGIN_X - 210, y + 10, 210, 46, date or "latest", PALETTE["soft_blue"], PALETTE["blue"])
        y += 82

        if conclusion:
            lines = self._wrap(conclusion, self.fonts["section"], CANVAS_SIZE[0] - MARGIN_X * 2)
            for line in lines[:2]:
                self.draw.text((MARGIN_X, y), line, font=self.fonts["section"], fill=PALETTE["red"])
                y += 44

        compact_summary = self._compact_hero_summary(summary)
        for line in self._wrap(compact_summary, self.fonts["body"], CANVAS_SIZE[0] - MARGIN_X * 2)[:3]:
            self.draw.text((MARGIN_X, y), line, font=self.fonts["body"], fill=PALETTE["muted"])
            y += 34

        return y + 28

    def _render_flow_block(self, y: int) -> int:
        blocks = dict(self.payload.get("image_blocks", {}) or {})
        flow_block = dict(blocks.get("flow_block", {}) or {})
        items = list(flow_block.get("items", []) or [])[:4]
        y = self._section_title(y, str(flow_block.get("title", "")).strip() or "钱的方向")

        col_gap = 20
        row_gap = 18
        col_width = (CANVAS_SIZE[0] - MARGIN_X * 2 - col_gap) // 2
        card_h = 140
        for idx, item in enumerate(items):
            col = idx % 2
            row = idx // 2
            x = MARGIN_X + col * (col_width + col_gap)
            cy = y + row * (card_h + row_gap)
            self._render_flow_card(x, cy, col_width, card_h, dict(item or {}))
        return y + 2 * card_h + row_gap + SECTION_GAP

    def _render_flow_card(self, x: int, y: int, width: int, height: int, item: dict[str, Any]) -> None:
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        tone = PALETTE["soft_blue"]
        ink = PALETTE["blue"]
        if "流出" in title:
            tone = PALETTE["soft_green"]
            ink = PALETTE["green"]
        elif "矛盾" in title:
            tone = PALETTE["soft_gold"]
            ink = PALETTE["gold"]
        elif "保留" in title:
            tone = PALETTE["panel"]
            ink = PALETTE["red"]
        self._round_rect((x, y, x + width, y + height), radius=18, fill=tone, outline=PALETTE["hairline"])
        self.draw.text((x + 20, y + 18), title, font=self.fonts["item_title"], fill=ink)
        sy = y + 56
        for line in self._wrap(summary, self.fonts["small"], width - 40)[:3]:
            self.draw.text((x + 20, sy), line, font=self.fonts["small"], fill=PALETTE["ink"])
            sy += 27

    def _render_drivers_block(self, y: int) -> int:
        blocks = dict(self.payload.get("image_blocks", {}) or {})
        drivers_block = dict(blocks.get("drivers_block", {}) or {})
        news_items = list(drivers_block.get("items", []) or [])[:16]
        y = self._section_title(y, str(drivers_block.get("title", "")).strip() or "推动资金移动的事件")
        col_gap = 22
        col_width = (CANVAS_SIZE[0] - MARGIN_X * 2 - col_gap) // 2
        left_y = y
        right_y = y
        for idx, item in enumerate(news_items, start=1):
            if idx % 2 == 1:
                left_y = self._render_driver_item(MARGIN_X, left_y, col_width, idx, dict(item or {}))
            else:
                right_y = self._render_driver_item(MARGIN_X + col_width + col_gap, right_y, col_width, idx, dict(item or {}))
        return max(left_y, right_y) + SECTION_GAP

    def _render_driver_item(self, x: int, y: int, width: int, idx: int, item: dict[str, Any]) -> int:
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        source = str(item.get("source", "")).strip()
        if not title:
            return y

        number = f"{idx:02d}"
        self._draw_pill(x, y + 2, 48, 30, number, PALETTE["soft_red"], PALETTE["red"])
        text_x = x + 62
        max_width = width - 62
        for line in self._wrap(title, self.fonts["item_title"], max_width)[:2]:
            self.draw.text((text_x, y), line, font=self.fonts["item_title"], fill=PALETTE["ink"])
            y += 32
        if summary:
            for line in self._wrap(summary, self.fonts["small"], max_width)[:1]:
                self.draw.text((text_x, y), line, font=self.fonts["small"], fill=PALETTE["muted"])
                y += 25
        if source:
            self.draw.text((text_x, y), source, font=self.fonts["small"], fill=PALETTE["blue"])
            y += 24
        return y + 16

    def _render_data_block(self, y: int) -> int:
        blocks = dict(self.payload.get("image_blocks", {}) or {})
        data_block = dict(blocks.get("data_block", {}) or {})
        groups = list(data_block.get("groups", []) or [])
        y = self._section_title(y, str(data_block.get("title", "")).strip() or "全市场证据")

        col_gap = 22
        col_width = (CANVAS_SIZE[0] - MARGIN_X * 2 - col_gap) // 2
        start_y = y
        column_bottoms = [start_y, start_y]
        for idx, group in enumerate(groups[:5]):
            col = idx % 2
            x = MARGIN_X + col * (col_width + col_gap)
            current_y = column_bottoms[col]
            column_bottoms[col] = self._render_data_group(x, current_y, col_width, dict(group or {}))
        return max(column_bottoms) + SECTION_GAP

    def _render_data_group(self, x: int, y: int, width: int, group: dict[str, Any]) -> int:
        label = str(group.get("label", "")).strip()
        items = list(group.get("items", []) or [])[:16]
        panel_h = 46 + len(items) * 35 + 24
        self._round_rect((x, y, x + width, y + panel_h), radius=20, fill=PALETTE["panel"], outline=PALETTE["hairline"])
        self.draw.text((x + 22, y + 16), label, font=self.fonts["item_title"], fill=PALETTE["blue"])
        y += 58
        for item in items:
            title = str(dict(item or {}).get("title", "")).strip()
            if not title:
                continue
            color = self._move_color(title)
            left, right = self._split_market_title(title)
            self.draw.text((x + 22, y), left, font=self.fonts["body"], fill=PALETTE["ink"])
            value_w = int(self.draw.textlength(right, font=self.fonts["number"])) if right else 0
            if right:
                self.draw.text((x + width - 22 - value_w, y), right, font=self.fonts["number"], fill=color)
            y += 35
        return y + 22

    def _render_mapping_block(self, y: int) -> int:
        blocks = dict(self.payload.get("image_blocks", {}) or {})
        mapping_block = dict(blocks.get("mapping_block", {}) or {})
        items = list(mapping_block.get("items", []) or [])[:5]
        y = self._section_title(y, str(mapping_block.get("title", "")).strip() or "接下来盯哪里")
        for item in items:
            title = str(dict(item or {}).get("title", "")).strip()
            summary = str(dict(item or {}).get("summary", "")).strip()
            if not title:
                continue
            self.draw.text((MARGIN_X, y), title, font=self.fonts["item_title"], fill=PALETTE["gold"])
            y += 35
            for line in self._wrap(summary, self.fonts["small"], CANVAS_SIZE[0] - MARGIN_X * 2)[:2]:
                self.draw.text((MARGIN_X, y), line, font=self.fonts["small"], fill=PALETTE["muted"])
                y += 27
            y += 12
        return y

    def _render_footer(self, y: int) -> int:
        meta = dict(self.payload.get("meta", {}) or {})
        source_count = str(meta.get("source_count", "")).strip()
        footer = f"数据源 {source_count or '-'} 个 · 新闻/市场/预测/仓位信号自动汇总 · 只做隔夜资金和事件整理，不给买卖建议"
        self.draw.line((MARGIN_X, y, CANVAS_SIZE[0] - MARGIN_X, y), fill=PALETTE["hairline"], width=2)
        self.draw.text((MARGIN_X, y + 23), footer, font=self.fonts["small"], fill=PALETTE["muted"])
        return y + 64

    def _section_title(self, y: int, title: str) -> int:
        self.draw.line((MARGIN_X, y, CANVAS_SIZE[0] - MARGIN_X, y), fill=PALETTE["hairline"], width=2)
        y += 18
        self.draw.text((MARGIN_X, y), title, font=self.fonts["section"], fill=PALETTE["ink"])
        return y + 52

    def _draw_pill(self, x: int, y: int, w: int, h: int, text: str, fill: str, ink: str) -> None:
        self._round_rect((x, y, x + w, y + h), radius=h // 2, fill=fill, outline=None)
        text_w = self.draw.textlength(text, font=self.fonts["badge"])
        self.draw.text((x + (w - text_w) / 2, y + 9), text, font=self.fonts["badge"], fill=ink)

    def _round_rect(self, box: tuple[int, int, int, int], *, radius: int, fill: str, outline: str | None) -> None:
        self.draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 1)

    def _wrap(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
        clean = re.sub(r"\s+", " ", str(text or "").strip())
        if not clean:
            return []
        lines: list[str] = []
        current = ""
        for char in clean:
            candidate = current + char
            if self.draw.textlength(candidate, font=font) <= max_width or not current:
                current = candidate
                continue
            lines.append(current.rstrip())
            current = char.lstrip()
        if current:
            lines.append(current.rstrip())
        return lines

    def _compact_hero_summary(self, summary: str) -> str:
        text = str(summary or "").strip()
        text = text.replace("新闻：", "驱动：").replace(" 数据：", "；价格：")
        return text

    def _split_market_title(self, title: str) -> tuple[str, str]:
        match = re.search(r"(.+?)\s+([+-]\d+(?:\.\d+)?%|偏上|偏下|震荡)$", title)
        if not match:
            return title, ""
        return match.group(1), match.group(2)

    def _move_color(self, title: str) -> str:
        if "偏下" in title or re.search(r"-\d", title):
            return PALETTE["green"]
        if "偏上" in title or re.search(r"\+\d", title):
            return PALETTE["red"]
        return PALETTE["muted"]

    def _font(self, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.font_path, size=size)

    def _resolve_font_path(self) -> str:
        for candidate in FONT_CANDIDATES:
            if Path(candidate).exists():
                return candidate
        return "/System/Library/Fonts/Helvetica.ttc"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render world money flow JSON payload to PNG.")
    parser.add_argument("input_json", help="Path to world_money_flow image payload JSON")
    parser.add_argument("output_png", help="Path to output PNG")
    args = parser.parse_args()
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    output = render_world_money_flow_png(payload, args.output_png)
    print(output)


if __name__ == "__main__":
    main()
