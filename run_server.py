"""启动 FastAPI 后端服务

强制 workers=1（baostock 全局登录状态并发不安全，必须串行）。

用法：
  python run_server.py

  python run_server.py --port 9000
  python run_server.py --reload   # 开发模式（仍是单 worker）
"""
import argparse
import os
import sys

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="A股量化交易 API 服务")
    parser.add_argument("--host", default=os.environ.get("QUANT_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("QUANT_API_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="开发模式：自动重载（仍是单 worker）")
    parser.add_argument("--log-level", default=os.environ.get("QUANT_LOG_LEVEL", "info").lower())
    args = parser.parse_args()

    # 强制 workers=1（关键约束）
    workers = 1
    if args.reload and workers != 1:
        print("[warn] reload 模式强制单 worker")

    print(f"启动 A股量化交易 API")
    print(f"  地址: http://{args.host}:{args.port}")
    print(f"  文档: http://{args.host}:{args.port}/docs")
    print(f"  workers: {workers}（强制：baostock 全局登录状态）")
    print(f"  reload: {args.reload}")
    print()

    uvicorn.run(
        "src.api.app:create_app",
        host=args.host,
        port=args.port,
        workers=workers,
        reload=args.reload,
        log_level=args.log_level,
        factory=True,
    )


if __name__ == "__main__":
    main()
