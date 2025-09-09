import subprocess
import uiautomator2 as u2
import time
import os  # 新增：用于处理路径
from conf import GlobalConfig
from util.log_util import TempLog


class Uiautomator:
    def __init__(self, device_id: str, log_util=None):
        self.device_id = device_id
        self.log = log_util or TempLog()
        self.atx_version = GlobalConfig["device"]["atx_version"]
        self.initialized = False  # 初始化状态标记
        self._d = None  # 新增：存储 uiautomator2.Device 实例（后续操作需用）
        self._init_device()  # 初始化设备（失败则抛出异常）

    def _init_device(self) -> None:
        """初始化设备（改用命令行调用 uiautomator2 init，兼容2.16.14版本）"""
        try:
            self.log.info(f"开始初始化设备：{self.device_id}（基于 uiautomator2==2.16.14）")

            # 1. 检查ADB设备是否在线（保留原逻辑）
            if not self._is_device_online():
                raise ConnectionError(f"设备{self.device_id}未在线（请检查ADB连接）")

            # 2. 关键修复：通过 subprocess 调用 python -m uiautomator2 init（复用日志中验证过的命令）
            init_cmd = [
                sys.executable,  # 用当前Python解释器（避免环境冲突）
                "-m", "uiautomator2", "init",  # uiautomator2 init 命令
                self.device_id  # 目标设备ID
            ]
            self.log.info(f"执行初始化命令：{' '.join(init_cmd)}")
            result = subprocess.run(
                init_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60  # 超时60秒，避免卡住
            )

            # 检查命令执行结果
            if result.returncode != 0:
                raise RuntimeError(
                    f"uiautomator2 init 执行失败！\n"
                    f" stdout: {result.stdout}\n"
                    f" stderr: {result.stderr}"
                )
            self.log.debug(f"uiautomator2 init 执行成功：\n{result.stdout}")

            # 3. 连接设备（初始化后必须通过 u2.connect 获取设备实例，后续操作依赖它）
            import uiautomator2 as u2  # 延迟导入，避免初始化前加载
            self._d = u2.connect(self.device_id)
            if not self._d.alive:
                raise ConnectionError(f"设备{self.device_id}连接失败（init成功但无法连接）")

            # 4. 保留原 atx-agent 版本校验逻辑（确保兼容性）
            self._check_atx_version()

            self.initialized = True
            self.log.info(f"设备{self.device_id}初始化成功（uiautomator2 版本：{u2.__version__}）")
        except Exception as e:
            self.log.error(f"设备{self.device_id}初始化失败：{str(e)}", exc_info=True)
            raise

    # ------------------- 新增：atx-agent 版本校验（复用原逻辑，依赖 self._d） -------------------
    def _check_atx_version(self) -> None:
        """通过 uiautomator2.Device 实例校验 atx-agent 版本"""
        try:
            # 调用设备实例的 atx_version 属性获取版本
            actual_version = self._d.atx_version
            if self.atx_version not in actual_version:
                raise RuntimeError(
                    f"atx-agent版本不匹配（期望{self.atx_version}，实际：{actual_version}）"
                )
            self.log.info(f"atx-agent版本校验通过：{actual_version}")
        except Exception as e:
            raise RuntimeError(f"atx-agent版本校验失败：{str(e)}") from e

    # ------------------- 设备控制接口（基于 uiautomator2 重写，保留原有参数和返回值） -------------------
    def screen_on(self) -> bool:
        """亮屏（基于 uiautomator2 重写）"""
        if not self.initialized:
            raise RuntimeError(f"设备{self.device_id}未初始化，无法执行亮屏操作")
        try:
            self._d.screen_on()  # 官方亮屏方法
            self.log.info(f"设备{self.device_id}执行亮屏操作")
            return True
        except Exception as e:
            self.log.error(f"设备{self.device_id}亮屏失败：{str(e)}", exc_info=True)
            return False

    def press(self, key: str) -> bool:
        """按键（如home、back，基于 uiautomator2 重写）"""
        key_map = {"home": "home", "back": "back", "power": "power"}  # uiautomator2 支持的按键名
        if key not in key_map:
            self.log.error(f"不支持的按键：{key}（支持：{list(key_map.keys())}）")
            return False
        try:
            self._d.press(key_map[key])  # 官方按键方法
            self.log.info(f"设备{self.device_id}执行按键操作：{key}")
            return True
        except Exception as e:
            self.log.error(f"设备{self.device_id}按键{key}失败：{str(e)}", exc_info=True)
            return False

    def check_text_exists(self, text: str) -> bool:
        """检查文本是否存在（基于 uiautomator2 重写，无需手动处理 xml  dump）"""
        if not self.initialized:
            raise RuntimeError(f"设备{self.device_id}未初始化，无法执行文本检查")
        try:
            # 官方文本查找：wait_timeout=2 表示等待2秒（避免界面未加载完成）
            exists = self._d(text=text).wait(exists=True, timeout=2)
            self.log.info(f"设备{self.device_id}检查文本'{text}'：{'存在' if exists else '不存在'}")
            return exists
        except Exception as e:
            self.log.error(f"设备{self.device_id}检查文本'{text}'失败：{str(e)}", exc_info=True)
            return False

    def click(self, x: int, y: int) -> bool:
        """点击坐标（基于 uiautomator2 重写，自带参数校验）"""
        if not self.initialized:
            raise RuntimeError(f"设备{self.device_id}未初始化，无法执行点击操作")
        if not (isinstance(x, int) and isinstance(y, int) and x >= 0 and y >= 0):
            self.log.error(f"点击坐标参数错误：x={x}（需非负int）, y={y}（需非负int）")
            return False
        try:
            self._d.click(x, y)  # 官方坐标点击方法
            self.log.info(f"设备{self.device_id}点击坐标：({x}, {y})")
            return True
        except Exception as e:
            self.log.error(f"设备{self.device_id}点击坐标({x},{y})失败：{str(e)}", exc_info=True)
            return False

    # ------------------- 新增：暴露 uiautomator2 Device 实例（可选，方便扩展） -------------------
    def get_device_instance(self) -> u2.Device:
        """获取 uiautomator2 原生 Device 实例（用于自定义扩展操作）"""
        if not self.initialized:
            raise RuntimeError(f"设备{self.device_id}未初始化，无法获取 Device 实例")
        return self._d