"""日志模块 - 记录应用运行日志到文件"""
import os
import sys
import logging
import traceback
from datetime import datetime


def setup_logger():
    """初始化日志系统，输出到文件和控制台"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")

    logger = logging.getLogger("data_analyzer")
    logger.setLevel(logging.DEBUG)

    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(file_fmt)
    logger.addHandler(console_handler)

    return logger


def setup_exception_hook(logger):
    """捕获未处理的异常，写入日志而不是直接崩溃"""
    def exception_hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical(f"未捕获的异常:\n{error_msg}")

    sys.excepthook = exception_hook
