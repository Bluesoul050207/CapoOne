"""
test_format_convert — 测试 Anthropic↔OpenAI 格式转换
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.format_convert import strip_emoji, _sanitize, anthropic_tools_to_openai, anthropic_msgs_to_openai


class TestStripEmoji:
    def test_no_emoji(self):
        assert strip_emoji("hello world") == "hello world"

    def test_strip_smile(self):
        text = "hello 😀 world"
        result = strip_emoji(text)
        assert "😀" not in result
        assert "hello" in result
        assert "world" in result

    def test_chinese_no_emoji(self):
        text = "你好世界"
        assert strip_emoji(text) == "你好世界"


class TestSanitize:
    def test_normal(self):
        assert _sanitize("hello") == "hello"

    def test_none(self):
        assert _sanitize(None) is None
        assert _sanitize("") == ""

    def test_chinese(self):
        assert _sanitize("你好") == "你好"


class TestToolsToOpenAI:
    def test_convert(self):
        tools = [{
            "name": "read_file",
            "description": "read a file",
            "input_schema": {
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
                "required": ["file_path"],
            }
        }]
        result = anthropic_tools_to_openai(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "read_file"
        assert result[0]["function"]["parameters"]["required"] == ["file_path"]


class TestMsgsToOpenAI:
    def test_simple_user(self):
        msgs = [{"role": "user", "content": "hello"}]
        result = anthropic_msgs_to_openai(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "hello"

    def test_assistant_with_tools(self):
        msgs = [{
            "role": "assistant",
            "content": "let me check",
            "tool_calls": [{"id": "1", "name": "read_file", "input": {"file_path": "/tmp/x"}}]
        }]
        result = anthropic_msgs_to_openai(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["tool_calls"][0]["function"]["name"] == "read_file"

    def test_tool_result(self):
        msgs = [{
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "1", "content": "file contents"}
            ]
        }]
        result = anthropic_msgs_to_openai(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "tool"
        assert result[0]["content"] == "file contents"
