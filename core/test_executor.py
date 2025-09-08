# @Time     : 2024/5/20 11:30
# @Author   : CN-LanBao
# -*- coding: utf-8 -*-
import os
import subprocess
import shutil
from datetime import datetime
from util.log_util import LogUtil, TempLog
from util.path_util import safe_join, ensure_dir_exists
from conf import GlobalConfig


class TestExecutor:
    def __init__(self, task_id: str, device_id: str, suite_abs_path: str):
        self.task_id = task_id
        self.device_id = device_id
        self.suite_abs_path = suite_abs_path
        self.log = LogUtil(
            device_id=device_id, task_id=task_id, logger_name=f"task_{task_id}"
        )

        # 初始化路径（基于配置的报告根目录）
        self.report_root = GlobalConfig["path"]["report_root_dir"]
        self.task_report_dir = safe_join(self.report_root, self.task_id)
        self.allure_raw_dir = safe_join(self.task_report_dir, "allure_raw")
        self.allure_html_dir = safe_join(self.task_report_dir, "allure_html")
        self.task_log_path = safe_join(self.task_report_dir, f"task_{task_id}.log")

    def prepare(self) -> None:
        """准备测试环境（清理旧目录、创建新目录）"""
        self.log.info(f"准备测试环境：{self.task_report_dir}")

        # 清理旧报告（避免残留）
        if os.path.exists(self.task_report_dir):
            shutil.rmtree(self.task_report_dir)
            self.log.warning(f"清理旧报告目录：{self.task_report_dir}")

        # 创建新目录
        ensure_dir_exists(self.allure_raw_dir)
        ensure_dir_exists(self.allure_html_dir)
        self.log.info(f"测试目录初始化完成：{self.task_report_dir}")

        # 校验用例路径
        if not os.path.exists(self.suite_abs_path):
            raise FileNotFoundError(f"测试用例不存在：{self.suite_abs_path}")
        if not os.path.isfile(self.suite_abs_path):
            raise ValueError(f"{self.suite_abs_path}不是有效文件")
        self.log.info(f"测试用例校验通过：{self.suite_abs_path}")

    def run_pytest(self) -> tuple[int, str, str]:
        """执行Pytest测试（生成Allure原始报告）"""
        self.log.info("开始执行Pytest测试...")

        # Pytest命令（带设备ID和任务ID参数，供conftest.py使用）
        pytest_cmd = [
            "python", "-m", "pytest",
            self.suite_abs_path,
            f"--device_id={self.device_id}",
            f"--task_id={self.task_id}",
            f"--alluredir={self.allure_raw_dir}",
            "-v",  # 详细日志
            "--tb=short",  # 精简堆栈
            f"--timeout={GlobalConfig['test']['pytest_timeout']}"  # 超时时间
        ]

        # 执行命令（捕获输出）
        result = subprocess.run(
            pytest_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=GlobalConfig["test"]["pytest_timeout"] + 60  # 预留60秒清理时间
        )

        # 保存执行日志
        with open(self.task_log_path, "w", encoding="utf-8") as f:
            f.write(f"=== 任务{self.task_id} Pytest执行日志 ===\n")
            f.write(f"执行命令：{' '.join(pytest_cmd)}\n")
            f.write(f"返回码：{result.returncode}\n")
            f.write(f"\n=== 标准输出（stdout）===\n{result.stdout}\n")
            f.write(f"\n=== 错误输出（stderr）===\n{result.stderr}\n")
        self.log.info(f"Pytest日志已保存：{self.task_log_path}")

        return result.returncode, result.stdout, result.stderr

    def generate_allure_report(self) -> str:
        """生成Allure HTML报告"""
        self.log.info("开始生成Allure HTML报告...")

        # Allure命令（清理旧报告）
        allure_cmd = [
            "allure", "generate",
            self.allure_raw_dir,
            "-o", self.allure_html_dir,
            "--clean" if GlobalConfig["test"]["allure_clean"] else ""
        ]
        # 过滤空参数（--clean为False时）
        allure_cmd = [cmd for cmd in allure_cmd if cmd]

        # 执行命令
        result = subprocess.run(
            allure_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        # 校验报告
        if result.returncode != 0:
            raise RuntimeError(f"Allure报告生成失败：{result.stderr[:500]}")

        index_html = safe_join(self.allure_html_dir, "index.html")
        if not os.path.exists(index_html):
            raise FileNotFoundError(f"报告入口文件不存在：{index_html}")

        self.log.info(f"Allure报告生成成功：{index_html}")
        return index_html

    def execute(self) -> dict:
        """完整执行测试流程（准备-执行-生成报告）"""
        try:
            self.prepare()

            # 执行Pytest
            pytest_returncode, pytest_stdout, pytest_stderr = self.run_pytest()

            # 生成报告（即使Pytest失败也生成报告）
            report_path = self.generate_allure_report()

            # 返回任务结果
            return {
                "status": "success" if pytest_returncode == 0 else "success_with_failure",
                "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "report_path": self.allure_html_dir,
                "log_path": self.task_log_path,
                "pytest_returncode": pytest_returncode,
                "pytest_stdout": pytest_stdout,
                "pytest_stderr": pytest_stderr
            }
        except subprocess.TimeoutExpired:
            error_msg = f"测试执行超时（超过{GlobalConfig['test']['pytest_timeout']}秒）"
            self.log.error(error_msg)
            return self._fail_result(error_msg)
        except Exception as e:
            error_msg = str(e)[:500]
            self.log.error(f"测试执行失败：{error_msg}", exc_info=True)
            return self._fail_result(error_msg)

    def _fail_result(self, error_msg: str) -> dict:
        """生成失败结果字典"""
        return {
            "status": f"failed: {error_msg}",
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_msg": error_msg,
            "log_path": self.task_log_path if os.path.exists(self.task_log_path) else None
        }