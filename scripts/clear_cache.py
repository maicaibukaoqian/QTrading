#!/usr/bin/env python
"""清理所有缓存数据"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from src.data.cache import clear_cache, get_cache_size


def main():
    size = get_cache_size()
    mb = size / (1024 * 1024)
    print(f"当前缓存大小: {mb:.2f} MB")

    clear_cache()
    print("缓存已清空")


if __name__ == '__main__':
    main()
