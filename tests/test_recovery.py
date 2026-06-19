"""
test_recovery — 测试 RECOVERY 字典匹配逻辑
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_loop import RECOVERY, _get_recovery


class TestRecoveryDict:
    def test_has_all_keys(self):
        assert "low_match" in RECOVERY
        assert "file_not_found" in RECOVERY
        assert "no_matches" in RECOVERY
        assert "access_denied" in RECOVERY
        assert "unknown_tool" in RECOVERY
        assert "timeout" in RECOVERY
        assert "not_found" in RECOVERY

    def test_all_values_non_empty(self):
        for key, val in RECOVERY.items():
            assert val.strip(), f"RECOVERY[{key}] is empty"


class TestGetRecovery:
    def test_exact_match(self):
        result = _get_recovery("low_match")
        assert result is not None
        assert "web_search" in result

    def test_case_insensitive(self):
        result = _get_recovery("LOW_MATCH")
        assert result is not None
        assert "web_search" in result

    def test_substring_match(self):
        """当精确匹配失败时，尝试子串匹配"""
        result = _get_recovery("access_denied_for_admin")
        assert result is not None
        assert "权限" in result

    def test_no_match(self):
        result = _get_recovery("some_unknown_error")
        assert result is None

    def test_empty_tag(self):
        assert _get_recovery("") is None
        assert _get_recovery(None) is None

    def test_whitespace_tag(self):
        assert _get_recovery("  ") is None

    def test_file_not_found(self):
        result = _get_recovery("file_not_found")
        assert "list_directory" in result

    def test_timeout(self):
        result = _get_recovery("timeout")
        assert "超时" in result
