from .read_file import ReadFileHandler
from .write_file import WriteFileHandler
from .list_dir import ListDirHandler
from .run_shell import RunShellHandler
from .search import SearchHandler
from .save_memory import SaveMemoryHandler
from .web import WebSearchHandler, WebFetchHandler
from .process import ProcessListHandler, ProcessKillHandler, ProcessStartHandler
from .clipboard import ClipboardReadHandler, ClipboardWriteHandler
from .screenshot import ScreenshotHandler
from .cmd_tools import CmdHelpHandler, CmdRunHandler
from .temp_rule import TempRuleHandler
from .move_file import MoveFileHandler
from .window import WindowListHandler, WindowMinimizeHandler
from .window_restore import WindowRestoreHandler
from .note import QuickNoteHandler
from .system_status import SystemStatusHandler
from .ncm_play import NcmPlayHandler
ALL_HANDLERS = [
    ReadFileHandler, WriteFileHandler, ListDirHandler,
    RunShellHandler, SearchHandler,
    SaveMemoryHandler,
    WebSearchHandler, WebFetchHandler,
    ProcessListHandler, ProcessKillHandler, ProcessStartHandler,
    ClipboardReadHandler, ClipboardWriteHandler,
    ScreenshotHandler,
    CmdHelpHandler, CmdRunHandler,
    TempRuleHandler,
    MoveFileHandler,
    WindowListHandler, WindowMinimizeHandler, WindowRestoreHandler,
    QuickNoteHandler,
    SystemStatusHandler,
    NcmPlayHandler,
]
