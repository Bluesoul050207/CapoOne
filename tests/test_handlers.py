"""
test_handlers — 测试不依赖外部 API 的工具 handler
"""
import sys
import tempfile
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.executor.handlers.read_file import ReadFileHandler
from modules.executor.handlers.write_file import WriteFileHandler
from modules.executor.handlers.list_dir import ListDirHandler
from modules.executor.handlers.search import SearchHandler
from modules.executor.tool_result import ToolResult


class TestReadFileHandler:
    def setup_method(self):
        self.handler = ReadFileHandler()
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        self.tmp.write("line1\nline2\nline3\n")
        self.tmp.close()

    def teardown_method(self):
        os.unlink(self.tmp.name)

    def test_basic_read(self):
        result = self.handler.execute({"file_path": self.tmp.name})
        assert isinstance(result, ToolResult)
        assert result.ok is True
        assert "line1" in result.text
        assert "line2" in result.text

    def test_offset_limit(self):
        result = self.handler.execute({"file_path": self.tmp.name, "offset": 1, "limit": 1})
        assert result.ok is True
        assert "line1" not in result.text  # offset=1 skips line1
        assert "line2" in result.text

    def test_file_not_found(self):
        result = self.handler.execute({"file_path": "/nonexistent/file.txt"})
        assert result.ok is False
        assert result.error == "file_not_found"


class TestWriteFileHandler:
    def setup_method(self):
        self.handler = WriteFileHandler()
        self.tmp_path = tempfile.mktemp(suffix=".txt")

    def teardown_method(self):
        if os.path.exists(self.tmp_path):
            os.unlink(self.tmp_path)

    def test_write(self):
        result = self.handler.execute({"file_path": self.tmp_path, "content": "hello world"})
        assert isinstance(result, ToolResult)
        assert result.ok is True
        assert os.path.exists(self.tmp_path)
        with open(self.tmp_path, "r") as f:
            assert f.read() == "hello world"

    def test_needs_confirm(self):
        need, msg = self.handler.needs_confirm({"file_path": "/tmp/x"})
        assert need is True
        assert "write:" in msg


class TestListDirHandler:
    def setup_method(self):
        self.handler = ListDirHandler()
        self.tmpdir = tempfile.mkdtemp()
        Path(self.tmpdir, "test_file.txt").touch()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list(self):
        result = self.handler.execute({"path": self.tmpdir})
        assert isinstance(result, ToolResult)
        assert result.ok is True
        assert "test_file.txt" in result.text

    def test_pattern(self):
        result = self.handler.execute({"path": self.tmpdir, "pattern": "*.py"})
        assert result.ok is True
        assert "test_file.txt" not in result.text  # filtered out

    def test_not_found(self):
        result = self.handler.execute({"path": "/nonexistent_dir_xyz"})
        assert result.ok is False
        assert result.error == "file_not_found"


class TestSearchHandler:
    def setup_method(self):
        self.handler = SearchHandler()
        self.tmpdir = tempfile.mkdtemp()
        with open(Path(self.tmpdir, "a.py"), "w") as f:
            f.write("def hello():\n    pass\n")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_search_found(self):
        result = self.handler.execute({"pattern": "def hello", "directory": self.tmpdir})
        assert isinstance(result, ToolResult)
        assert result.ok is True
        assert "def hello" in result.text

    def test_search_not_found(self):
        result = self.handler.execute({"pattern": "nonexistent_xyz", "directory": self.tmpdir})
        assert result.ok is False
        assert result.error == "no_matches"
