"""OpenCC 繁→简 转换（针对前端量衡錄）
OpenCC 的 t2s 配置含完整 通用规范 映射，比手写 dict 准。
"""
import sys
from pathlib import Path
from opencc import OpenCC

cc = OpenCC("t2s")

TARGETS = [
    "frontend/index.html",
    "frontend/js/app.js",
    "frontend/css/style.css",
]


def main():
    targets = sys.argv[1:] or TARGETS
    for path in targets:
        p = Path(path)
        if not p.exists():
            print(f"[skip] {path} not found")
            continue
        orig = p.read_text(encoding="utf-8")
        converted = cc.convert(orig)
        if converted == orig:
            print(f"[no-op] {path}")
        else:
            p.write_text(converted, encoding="utf-8")
            diff_chars = sum(1 for a, b in zip(orig, converted) if a != b)
            print(f"[done]  {path}  ({diff_chars} chars changed)")


if __name__ == "__main__":
    main()
