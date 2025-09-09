# @Time     : 2024/5/20 10:30
# @Author   : CN-LanBao
# -*- coding: utf-8 -*-
import subprocess
import time
from conf import GlobalConfig
from util.log_util import TempLog
import os


class Uiautomator:
    def __init__(self, device_id: str, log_util=None):
        self.device_id = device_id
        self.log = log_util or TempLog()
        self.atx_version = GlobalConfig["device"]["atx_version"]
        self.initialized = False  # 初始化状态标记
        self._init_device()  # 初始化设备（失败则抛出异常）

    def _init_device(self) -> None:
        """初始化设备（安装uiautomator apk、启动atx-agent）"""
        try:
            self.log.info(f"开始初始化设备：{self.device_id}")

            # 1. 检查ADB设备是否在线
            if not self._is_device_online():
                raise ConnectionError(f"设备{self.device_id}未在线（请检查ADB连接）")

            # 2. 安装uiautomator测试包（重试3次）
            self._install_uiautomator_apk(retries=3)

            # 3. 启动并校验atx-agent
            self._start_atx_agent()

            self.initialized = True
            self.log.info(f"设备{self.device_id}初始化成功")
        except Exception as e:
            self.log.error(f"设备{self.device_id}初始化失败：{str(e)}", exc_info=True)
            raise  # 向上抛出异常，避免返回None实例

    def _is_device_online(self) -> bool:
        """检查设备是否在线"""
        result = subprocess.run(
            [GlobalConfig["device"]["adb_path"], "-s", self.device_id, "get-state"],
            capture_output=True, text=True, encoding="utf-8"
        )
        return result.returncode == 0 and result.stdout.strip() == "device"

    def _install_uiautomator_apk(self, retries: int = 3) -> None:
        """安装uiautomator测试包（带重试，动态查找APK路径）"""
        # 定义APK类型与对应的缓存目录前缀
        apk_cache_prefix = {
            "app": "app-uiautomator.apk-",  # app包缓存目录前缀（如app-uiautomator.apk-d3f17174fb）
            "test": "app-uiautomator-test.apk-"  # test包缓存目录前缀（如app-uiautomator-test.apk-652bf9e13c）
        }
        uiautomator_cache_dir = "C:\\Users\\zyli\\.uiautomator2\\cache"  # 固定缓存根目录
        apk_paths = {}

        # 动态查找每个APK的真实路径
        for apk_type, prefix in apk_cache_prefix.items():
            # 1. 遍历缓存目录，找到以指定前缀开头的子目录
            try:
                # 获取缓存目录下所有以prefix开头的目录
                apk_dirs = [
                    d for d in os.listdir(uiautomator_cache_dir)
                    if os.path.isdir(os.path.join(uiautomator_cache_dir, d)) and d.startswith(prefix)
                ]
                if not apk_dirs:
                    raise FileNotFoundError(f"未找到{uiautomator_cache_dir}下以'{prefix}'开头的APK缓存目录")

                # 取最新的目录（按修改时间排序，取最后一个）
                apk_dir_path = os.path.join(uiautomator_cache_dir, max(apk_dirs, key=lambda x: os.path.getmtime(
                    os.path.join(uiautomator_cache_dir, x))))

                # 拼接APK文件路径（子目录下的APK文件名与前缀去掉版本后的名称一致）
                apk_filename = prefix.rstrip("-")  # 如"app-uiautomator.apk-" → "app-uiautomator.apk"
                apk_path = os.path.join(apk_dir_path, apk_filename)

                # 验证APK文件是否存在
                if not os.path.exists(apk_path):
                    raise FileNotFoundError(f"APK文件不存在：{apk_path}")

                apk_paths[apk_type] = apk_path
                self.log.info(f"找到{uiautomator_cache_dir}包的真实路径：{apk_path}")
            except Exception as e:
                raise FileNotFoundError(f"获取uiautomator {apk_type}包路径失败：{str(e)}") from e

        # 后续安装逻辑保持不变（使用动态获取的apk_paths）
        for apk_type, apk_path in apk_paths.items():
            install_cmd = [
                GlobalConfig["device"]["adb_path"], "-s", self.device_id,
                "install", "-r", "-t", apk_path
            ]

            for retry in range(retries):
                result = subprocess.run(
                    install_cmd, capture_output=True, text=True, encoding="utf-8"
                )
                if result.returncode == 0 and "Success" in result.stdout:
                    self.log.info(f"uiautomator {apk_type}包安装成功（重试{retry}次）")
                    break
                if retry == retries - 1:
                    raise RuntimeError(
                        f"uiautomator {apk_type}包安装失败（重试{retries}次）：{result.stderr}"
                    )
                time.sleep(2)  # 重试间隔

    def _start_atx_agent(self) -> None:
        """启动atx-agent并校验版本（增加重试、异常处理、版本清洗）"""
        atx_agent_path = "/data/local/tmp/atx-agent"
        start_retries = 3  # 启动命令重试次数
        version_retries = 3  # 版本校验重试次数

        # 1. 先检查atx-agent文件是否存在且有执行权限
        check_cmd = [
            GlobalConfig["device"]["adb_path"], "-s", self.device_id,
            "shell", f"test -x {atx_agent_path} && echo 'exists' || echo 'not exists'"
        ]
        check_result = subprocess.run(check_cmd, capture_output=True, text=True, encoding="utf-8")
        if check_result.returncode != 0 or "exists" not in check_result.stdout:
            raise FileNotFoundError(
                f"atx-agent文件缺失或无执行权限：{atx_agent_path}\n"
                f"建议执行命令重新推送：python -m uiautomator2 init {self.device_id}"
            )

        # 2. 停止旧进程（避免端口占用）
        stop_cmd = [
            GlobalConfig["device"]["adb_path"], "-s", self.device_id,
            "shell", f"{atx_agent_path}", "server", "--stop"
        ]
        subprocess.run(stop_cmd, capture_output=True, text=True, encoding="utf-8")
        self.log.info("已停止旧的atx-agent进程")

        # 3. 启动新进程（带重试）
        start_cmd = [
            GlobalConfig["device"]["adb_path"], "-s", self.device_id,
            "shell", f"{atx_agent_path}", "server", "--nouia", "-d", "--addr", "127.0.0.1:7912"
        ]
        start_success = False
        for retry in range(start_retries):
            start_result = subprocess.run(
                start_cmd, capture_output=True, text=True, encoding="utf-8"
            )
            # 启动命令无输出且返回码为0，视为启动成功（atx-agent后台启动无stdout）
            if start_result.returncode == 0 and not start_result.stderr:
                start_success = True
                self.log.info(f"atx-agent启动成功（重试{retry}次）")
                time.sleep(3)  # 延长等待时间，确保进程完全启动（原2秒可能不足）
                break
            if retry == start_retries - 1:
                raise RuntimeError(
                    f"atx-agent启动失败（重试{start_retries}次）：{start_result.stderr.strip()}"
                )
            time.sleep(2)  # 重试间隔

        # 4. 校验版本（带重试+输出清洗）
        actual_version = ""
        for retry in range(version_retries):
            version_cmd = [
                GlobalConfig["device"]["adb_path"], "-s", self.device_id,
                "shell", f"{atx_agent_path}", "version"
            ]
            version_result = subprocess.run(
                version_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore"  # 忽略编码错误
            )
            # 清洗输出：去除空行、空格，提取版本号（如"0.10.0"）
            cleaned_output = "".join(version_result.stdout.strip().split())
            # 简单版本号校验（匹配x.y.z格式）
            import re
            version_match = re.search(r"\d+\.\d+\.\d+", cleaned_output)
            if version_match:
                actual_version = version_match.group()
                break
            if retry == version_retries - 1:
                raise RuntimeError(
                    f"atx-agent版本获取失败（重试{version_retries}次）\n"
                    f"命令输出：{cleaned_output or '空输出'}\n"
                    f"命令错误：{version_result.stderr.strip() or '无错误'}"
                )
            time.sleep(1)  # 版本校验重试间隔

        # 5. 最终版本匹配
        if actual_version != self.atx_version:
            raise RuntimeError(
                f"atx-agent版本不匹配（期望{self.atx_version}，实际：{actual_version}）\n"
                f"建议执行命令更新：python -m uiautomator2 update {self.device_id}"
            )
        self.log.info(f"atx-agent版本校验通过：期望{self.atx_version}，实际{actual_version}")

    # ------------------- 设备控制接口（原功能保留，增加状态校验） -------------------
    def screen_on(self) -> bool:
        """亮屏（增加初始化状态校验）"""
        if not self.initialized:
            raise RuntimeError(f"设备{self.device_id}未初始化，无法执行亮屏操作")
        try:
            cmd = [
                GlobalConfig["device"]["adb_path"], "-s", self.device_id,
                "shell", "input", "keyevent", "224"  # 224=KEYCODE_POWER
            ]
            subprocess.run(cmd, capture_output=True)
            self.log.info(f"设备{self.device_id}执行亮屏操作")
            return True
        except Exception as e:
            self.log.error(f"设备{self.device_id}亮屏失败：{str(e)}", exc_info=True)
            return False

    def press(self, key: str) -> bool:
        """按键（如home、back）"""
        key_map = {"home": 3, "back": 4, "power": 224}
        if key not in key_map:
            self.log.error(f"不支持的按键：{key}（支持：{list(key_map.keys())}）")
            return False
        try:
            cmd = [
                GlobalConfig["device"]["adb_path"], "-s", self.device_id,
                "shell", "input", "keyevent", str(key_map[key])
            ]
            subprocess.run(cmd, capture_output=True)
            self.log.info(f"设备{self.device_id}执行按键操作：{key}")
            return True
        except Exception as e:
            self.log.error(f"设备{self.device_id}按键{key}失败：{str(e)}", exc_info=True)
            return False

    def check_text_exists(self, text: str) -> bool:
        """检查文本是否存在（基于uiautomator）"""
        try:
            cmd = [
                GlobalConfig["device"]["adb_path"], "-s", self.device_id,
                "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"
            ]
            subprocess.run(cmd, capture_output=True)

            # 读取并检查文本
            pull_cmd = [
                GlobalConfig["device"]["adb_path"], "-s", self.device_id,
                "pull", "/sdcard/window_dump.xml", "/tmp/"
            ]
            subprocess.run(pull_cmd, capture_output=True)

            with open("/tmp/window_dump.xml", "r", encoding="utf-8") as f:
                content = f.read()
            exists = text in content
            self.log.info(f"设备{self.device_id}检查文本'{text}'：{'存在' if exists else '不存在'}")
            return exists
        except Exception as e:
            self.log.error(f"设备{self.device_id}检查文本'{text}'失败：{str(e)}", exc_info=True)
            return False

    def click(self, x: int, y: int) -> bool:
        """点击坐标（修复原单参数bug）"""
        if not (isinstance(x, int) and isinstance(y, int)):
            self.log.error(f"点击坐标参数错误：x={x}（需int）, y={y}（需int）")
            return False
        try:
            cmd = [
                GlobalConfig["device"]["adb_path"], "-s", self.device_id,
                "shell", "input", "tap", str(x), str(y)
            ]
            subprocess.run(cmd, capture_output=True)
            self.log.info(f"设备{self.device_id}点击坐标：({x}, {y})")
            return True
        except Exception as e:
            self.log.error(f"设备{self.device_id}点击坐标({x},{y})失败：{str(e)}", exc_info=True)
            return False