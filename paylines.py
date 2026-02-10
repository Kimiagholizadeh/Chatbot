from __future__ import annotations

from typing import List


def generate_paylines(payline_count: int, reel_count: int, row_count: int) -> List[List[int]]:
    """Generate simple deterministic paylines.

    Each payline = list[row_index_per_reel].
    For a 5x3 game: row indices are 0..2.
    """
    if payline_count <= 0:
        return []

    lines: List[List[int]] = []
    mid = (row_count // 2) % row_count

    # baseline patterns
    base_patterns: List[List[int]] = []
    base_patterns.append([mid] * reel_count)  # straight middle
    if row_count >= 2:
        base_patterns.append([0] * reel_count)  # top
        base_patterns.append([row_count - 1] * reel_count)  # bottom
    if row_count >= 3 and reel_count >= 5:
        base_patterns.append([0, 1, 2, 1, 0][:reel_count])  # V
        base_patterns.append([2, 1, 0, 1, 2][:reel_count])  # inverted V

    # fill with patterned variations
    i = 0
    while len(lines) < payline_count:
        if i < len(base_patterns):
            lines.append(base_patterns[i])
        else:
            # diagonal / zigzag variants
            mode = i % 4
            line: List[int] = []
            for col in range(reel_count):
                if mode == 0:
                    row = col % row_count
                elif mode == 1:
                    row = (row_count - 1 - col) % row_count
                elif mode == 2:
                    row = (mid + ((-1) ** col)) % row_count
                else:
                    row = (mid + (1 if col % 3 == 0 else -1)) % row_count
                line.append(int(row))
            lines.append(line)
        i += 1
    return lines
