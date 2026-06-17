from .read_file import ReadFileHandler
from .write_file import WriteFileHandler
from .list_dir import ListDirHandler
from .run_shell import RunShellHandler
from .search import SearchHandler
from .save_memory import SaveRuleHandler, SaveMemoryHandler
from .web import WebSearchHandler, WebFetchHandler
from .process import ProcessListHandler, ProcessKillHandler, ProcessStartHandler
from .clipboard import ClipboardReadHandler, ClipboardWriteHandler
from .screenshot import ScreenshotHandler
from .cmd_tools import CmdHelpHandler, CmdRunHandler
ALL_HANDLERS = [
    ReadFileHandler, WriteFileHandler, ListDirHandler,
    RunShellHandler, SearchHandler,
    SaveRuleHandler, SaveMemoryHandler,
    WebSearchHandler, WebFetchHandler,
    ProcessListHandler, ProcessKillHandler, ProcessStartHandler,
    ClipboardReadHandler, ClipboardWriteHandler,
    ScreenshotHandler,
    CmdHelpHandler, CmdRunHandler,
]
