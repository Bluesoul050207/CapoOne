"""
test_tool_result — 测试 ToolResult 值对象
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.executor.tool_result import ToolResult


class TestToolResult:
    def test_success(self):
        r = ToolResult.success("done")
        assert r.ok is True
        assert r.text == "done"
        assert r.error is None

    def test_fail(self):
        r = ToolResult.fail("bad", "low_match")
        assert r.ok is False
        assert r.text == "bad"
        assert r.error == "low_match"

    def test_fail_no_tag(self):
        r = ToolResult.fail("something wrong")
        assert r.ok is False
        assert r.error is None

    def test_from_any_str(self):
        """str 自动转为 ok=True 的 ToolResult"""
        r = ToolResult.from_any("hello")
        assert r.ok is True
        assert r.text == "hello"

    def test_from_any_toolresult(self):
        """ToolResult 传入不变"""
        orig = ToolResult.fail("err", "timeout")
        r = ToolResult.from_any(orig)
        assert r is orig  # 同一个对象
        assert r.ok is False
        assert r.error == "timeout"

    def test_bool(self):
        assert bool(ToolResult.success("x")) is True
        assert bool(ToolResult.fail("x")) is False

    def test_str(self):
        assert str(ToolResult.success("abc")) == "abc"
        assert str(ToolResult.fail("err")) == "err"
