# @Time     : 2024/5/20 10:30
# @Author   : CN-LanBao
# -*- coding: utf-8 -*-
import subprocess
import time
from conf import GlobalConfig
from util.log_util import TempLog


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
        """安装uiautomator测试包（带重试）"""
        apk_paths = {
            "app": "C:\\Users\\zyli\\.uiautomator2\\cache\\app-uiautomator.apk",
            "test": "C:\\Users\\zyli\\.uiautomator2\\cache\\app-uiautomator-test.apk"
        }

        for apk_type, apk_path in apk_paths.items():
            if not os.path.exists(apk_path):
                raise FileNotFoundError(f"uiautomator {apk_type}包不存在：{apk_path}")

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
        """启动atx-agent并校验版本"""
        # 停止旧进程
        stop_cmd = [
            GlobalConfig["device"]["adb_path"], "-s", self.device_id,
            "shell", "/data/local/tmp/atx-agent", "server", "--stop"
        ]
        subprocess.run(stop_cmd, capture_output=True)

        # 启动新进程
        start_cmd = [
            GlobalConfig["device"]["adb_path"], "-s", self.device_id,
            "shell", "/data/local/tmp/atx-agent", "server", "--nouia", "-d", "--addr", "127.0.0.1:7912"
        ]
        result = subprocess.run(start_cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(f"atx-agent启动失败：{result.stderr}")

        # 校验版本（等待2秒确保进程启动）
        time.sleep(2)
        version_cmd = [
            GlobalConfig["device"]["adb_path"], "-s", self.device_id,
            "shell", "/data/local/tmp/atx-agent", "version"
        ]
        result = subprocess.run(version_cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0 or self.atx_version not in result.stdout:
            raise RuntimeError(
                f"atx-agent版本不匹配（期望{self.atx_version}，实际：{result.stdout.strip()}）"
            )
        self.log.info(f"atx-agent版本校验通过：{self.atx_version}")

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