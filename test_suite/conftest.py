# @Time     : 2022/5/10 9:55
# @Author   : CN-LanBao
# -*- coding: utf-8 -*-
import os
import sys
import pytest
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from core.uiautomator import Uiautomator


d = None



# 1. 注册命令行参数（让 pytest 识别 --device_id 和 --task_id）
def pytest_addoption(parser):
    parser.addoption(
        "--device_id",
        action="store",
        required=True,
        help="Android 设备 ID（通过 adb devices 查看）"
    )
    parser.addoption(
        "--task_id",
        action="store",
        required=True,
        help="测试任务 ID（用于日志和报告命名）"
    )

# 2. 定义 fixture，供用例获取参数
@pytest.fixture(scope="session")
def device_id(request):
    return request.config.getoption("--device_id")

@pytest.fixture(scope="session")
def task_id(request):
    return request.config.getoption("--task_id")


# TODO 若从文件中读取 id，用装饰器 @pytest.mark.parametrize("d", d)
@pytest.fixture(scope="function")
def setup_and_teardown_demo(device_id):
    """
    通用前置：亮屏
    通用收尾：回到主页面
    d 为 UI 测试的核心对象，除非知道后果否则请勿修改
    @Author: CN-LanBao
    @Create: 2022/5/9 17:32
    :return: Uiautomator
    """
    d.screen_on()
    yield d
    d.press("home")
