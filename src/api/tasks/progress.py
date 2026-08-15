"""进度上报 + 捕获 stdout

ProgressReporter：把进度/日志/步骤写回 Task
StdoutTee：redirect_stdout，把 screener 内部的 print 同时输出到控制台和 Task.logs
"""

import re
import sys
from contextlib import contextmanager, redirect_stdout


class TaskCancelled(Exception):
    """用户请求取消时抛出"""
    pass


class ProgressReporter:
    """进度上报器

    base/span：用于把内部 [0..100] 的进度映射到外层 [base..base+span]
    例如 download_all 把 universe 段 0-5%、fundamentals 5-50%、klines 50-100%
    """

    def __init__(self, store, task_id: str, base: int = 0, span: int = 100, echo: bool = False):
        self.store = store
        self.task_id = task_id
        self.base = base
        self.span = span
        self.echo = echo  # CLI 模式：直接 print 到控制台

    def set(self, pct: int, step: str = ""):
        """设置百分比 [0..100]"""
        pct = max(0, min(100, int(pct)))
        outer = self.base + int(pct * self.span / 100)
        kwargs = {"progress": outer}
        if step:
            kwargs["step"] = step
        self.store.update(self.task_id, **kwargs)
        if self.echo and step:
            print(f"[{self.task_id[:6]}] [{pct:3d}%] {step}", flush=True)

    def step(self, text: str):
        """只更新 step 文字，进度不变"""
        self.store.update(self.task_id, step=text)
        if self.echo:
            print(f"[{self.task_id[:6]}] {text}", flush=True)

    def log(self, line: str):
        """追加一行日志"""
        with self.store._lock:
            t = self.store._tasks.get(self.task_id)
            if t is not None:
                t.append_log(line)
        if self.echo:
            print(f"[{self.task_id[:6]}] {line}", flush=True)

    def advance(self, i: int, total: int, step_text: str = ""):
        """便捷：基于 i/total 算百分比"""
        if total <= 0:
            return
        pct = int(i * 100 / total)
        if step_text:
            self.set(pct, f"{step_text} {i}/{total}")
        else:
            self.set(pct, f"{i}/{total}")

    def sub(self, base: int, span: int) -> "ProgressReporter":
        """生成子区间 reporter，用于分段进度"""
        # 转换到外层坐标
        outer_base = self.base + int(base * self.span / 100)
        return ProgressReporter(self.store, self.task_id, base=outer_base, span=span, echo=self.echo)

    def check_cancel(self):
        """检查是否请求取消，抛 TaskCancelled"""
        with self.store._lock:
            t = self.store._tasks.get(self.task_id)
            if t is not None and t.cancel_requested:
                raise TaskCancelled(f"任务 {self.task_id} 已被用户取消")


# 匹配 screener 的 print 格式：[xxx-screen] 进度 1234/5382, 已下载 100, 跳过 200, 失败 10
_PROGRESS_RE = re.compile(r"进度\s+(\d+)\s*/\s*(\d+)")


class StdoutTee:
    """把 stdout 一份写到原 stdout，一份写到 ProgressReporter + 解析进度

    用法：
        with redirect_stdout(StdoutTee(reporter)):
            screener.screen(universe)
    """

    def __init__(self, reporter: ProgressReporter, original_stdout=None):
        self.reporter = reporter
        self._original = original_stdout or sys.stdout
        self._buf = ""

    def write(self, s: str) -> int:
        self._original.write(s)
        self._original.flush()

        # 缓存按行
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.rstrip("\r")
            if not line.strip():
                continue
            self.reporter.log(line)
            m = _PROGRESS_RE.search(line)
            if m:
                i, total = int(m.group(1)), int(m.group(2))
                self.reporter.advance(i, total)
        return len(s)

    def flush(self):
        self._original.flush()

    def isatty(self):
        return getattr(self._original, "isatty", lambda: False)()

    # 兼容一些库的 attribute access
    def __getattr__(self, name):
        return getattr(self._original, name)


@contextmanager
def tee_stdout(reporter: ProgressReporter):
    """便捷上下文管理器：把 stdout 重定向到 StdoutTee"""
    tee = StdoutTee(reporter)
    with redirect_stdout(tee):
        try:
            yield tee
        finally:
            # flush 残留
            if tee._buf.strip():
                reporter.log(tee._buf.strip())
                tee._buf = ""
