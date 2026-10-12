import logging
from utils.path_tool import get_abs_path
import os
from datetime import datetime

#日志保存的根目录
log_path = get_abs_path("logs")

#日志目录不存在则创建，存在则跳过
os.makedirs(log_path, exist_ok=True)

#日志格式配置 时间 - 日志器名称 - 日志级别 - 文件名:行号 - 日志信息
default_log_format = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

def get_logger(
        name: str = "agent", 
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        log_file: str = None,) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # 设置日志器的最低级别为DEBUG

#避免重复添加处理器（Handlers）
    if logger.handlers:
        return logger  # 如果已经有处理器，直接返回

    # 控制台处理器
    console_handler = logging.StreamHandler()  #流式输出
    console_handler.setLevel(console_level)  #日志级别
    console_handler.setFormatter(default_log_format)  #日志格式

    logger.addHandler(console_handler)

    #文件处理器
    if not log_file:
        log_file = os.path.join(log_path, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")

    file_handler = logging.FileHandler(log_file, encoding="utf-8") #
    file_handler.setLevel(file_level)
    file_handler.setFormatter(default_log_format)

    logger.addHandler(file_handler)

    return logger

#快捷获取日志
logger = get_logger()

if __name__ == "__main__":
    logger.info