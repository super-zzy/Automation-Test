import os
import logging
from datetime import datetime


class LogUtil:
    def __init__(self, device_id, task_id, logger_name="default"):
        """
        初始化 LogUtil，修复 log_dir 为 None 的问题
        :param device_id: 设备 ID（允许为 None，会自动替换为默认值）
        :param task_id: 任务 ID（允许为 None，会自动替换为默认值）
        :param logger_name: 日志器名称
        """
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

        # ------------------- 关键修复1：处理 device_id 和 task_id 为 None 的情况 -------------------
        # 若传入 None，用默认值替代（避免后续生成 log_dir 时为 None）
        self.device_id = device_id if (device_id is not None and str(device_id).strip()) else "unknown_device"
        self.task_id = task_id if (
                    task_id is not None and str(task_id).strip()) else f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # ------------------- 关键修复2：确保 log_dir 为有效路径 -------------------
        # 1. 生成基础日志目录（根据项目实际结构调整，确保根目录正确）
        # 假设日志目录在项目根目录下的 "logs" 文件夹（需与你的项目结构匹配）
        current_dir = os.path.dirname(os.path.abspath(__file__))  # util/ 目录
        project_root = os.path.dirname(current_dir)  # 项目根目录（util 的上级目录）
        base_log_dir = os.path.join(project_root, "logs")

        # 2. 生成当前任务的日志目录（基于 device_id 和 task_id）
        self.log_dir = os.path.join(base_log_dir, self.device_id, self.task_id)

        # 3. 校验 log_dir 有效性，若无效则用兜底路径
        if not isinstance(self.log_dir, (str, os.PathLike)) or not str(self.log_dir).strip():
            # 兜底路径：base_log_dir/default
            self.log_dir = os.path.join(base_log_dir, "default")
            print(f"⚠️ 日志目录生成无效，使用兜底路径：{self.log_dir}")

        # ------------------- 原有日志文件生成逻辑（保持不变，此时 log_dir 已有效） -------------------
        # 创建日志目录（不存在则创建）
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)

        # 生成日志文件名（如 20250908.log）
        file_name = f"{datetime.now().strftime('%Y%m%d')}.log"

        # 拼接日志文件路径（此时 log_dir 已确保为有效路径，不会报 None 错误）
        log_file_path = os.path.join(self.log_dir, file_name)  # 原报错行，现在已安全

        # 后续日志处理器配置（保持不变）
        if not self.logger.handlers:
            # 文件处理器
            file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            # 控制台处理器（可选，便于调试）
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            # 日志格式
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            # 添加处理器
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    # 原有日志方法（info/warning/error，保持不变）
    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)
