# @Time     : 2024/5/20 14:30
# @Author   : CN-LanBao
# -*- coding: utf-8 -*-
import os
import traceback
import uuid
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from threading import Thread
from core.test_executor import TestExecutor
from core.device_manager import DeviceManager
from util.log_util import TempLog
from util.path_util import safe_join

test_bp = Blueprint("test", __name__)
test_tasks = {}  # 全局任务状态缓存（task_id: 任务信息）
log = TempLog()


# ------------------- 工具函数 -------------------
def get_task_id() -> str:
    """生成唯一任务ID（毫秒级时间戳+4位随机字符串）"""
    time_part = datetime.now().strftime("%Y%m%d%H%M%S%f")[:13]
    random_part = str(uuid.uuid4()).replace("-", "")[:4]
    return f"{time_part}_{random_part}"


def get_test_suites() -> list[dict]:
    """获取测试用例列表（从配置的TEST_SUITE_DIR读取）"""
    try:
        test_suite_dir = current_app.config["TEST_SUITE_DIR"]
        log.info(f"开始获取测试用例，目录：{test_suite_dir}")

        # 确保用例目录存在
        if not os.path.exists(test_suite_dir):
            os.makedirs(test_suite_dir, exist_ok=True)
            log.warning(f"用例目录不存在，已自动创建：{test_suite_dir}")

        suites = []
        # 遍历目录，筛选.py文件（排除conftest.py）
        for root, _, files in os.walk(test_suite_dir):
            for name in files:
                if name.endswith(".py") and name != "conftest.py":
                    abs_path = safe_join(root, name)  # 安全路径拼接
                    rel_path = os.path.relpath(abs_path, test_suite_dir)
                    suites.append({
                        "id": len(suites),
                        "name": name,
                        "abs_path": abs_path,
                        "rel_path": rel_path
                    })

        log.info(f"获取用例完成，共{len(suites)}个可用用例")
        return suites
    except Exception as e:
        error_msg = f"获取用例列表失败：{str(e)}"
        log.error(error_msg, exc_info=True)
        return []


def run_task_background(task_id: str, device_id: str, suite_abs_path: str) -> None:
    """后台执行测试任务（独立线程）"""
    # 更新任务状态为"running"
    test_tasks[task_id]["status"] = "running"
    test_tasks[task_id]["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # 1. 获取设备实例（确保初始化成功）
        DeviceManager.get_uiautomator_instance(device_id, task_id)

        # 2. 执行测试
        executor = TestExecutor(task_id, device_id, suite_abs_path)
        task_result = executor.execute()

        # 3. 更新任务结果
        test_tasks[task_id].update(task_result)
    finally:
        # 4. 释放设备实例（无论成功失败）
        DeviceManager.release_device(device_id)


# ------------------- 接口定义 -------------------
@test_bp.get("/suites")
def get_test_suite_list():
    """获取测试用例列表接口"""
    try:
        log.info("收到测试用例列表查询请求")
        suites = get_test_suites()
        return jsonify({
            "code": 200,
            "msg": f"获取用例成功（共{len(suites)}个）",
            "data": suites
        })
    except Exception as e:
        error_msg = f"获取用例列表失败：{str(e)}"
        log.error(error_msg)
        return jsonify({
            "code": 400,
            "msg": error_msg,
            "data": []
        })


@test_bp.post("/start")
def start_test():
    """启动测试任务接口"""
    try:
        # 1. 解析请求参数
        req_data = request.get_json() or {}
        device_id = req_data.get("device_id")
        suite_id = req_data.get("suite_id")

        # 2. 参数校验
        if not device_id:
            return jsonify({"code": 400, "msg": "请指定设备ID", "data": None})
        if suite_id is None:
            return jsonify({"code": 400, "msg": "请指定用例ID", "data": None})

        # 3. 获取用例路径
        suites = get_test_suites()
        if suite_id < 0 or suite_id >= len(suites):
            return jsonify({"code": 404, "msg": f"用例ID{suite_id}不存在", "data": None})
        suite_info = suites[suite_id]

        # 4. 创建任务
        task_id = get_task_id()
        test_tasks[task_id] = {
            "task_id": task_id,
            "device_id": device_id,
            "suite_info": suite_info,
            "status": "pending",  # pending/running/success/failed
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 5. 后台启动任务（避免阻塞Web请求）
        Thread(
            target=run_task_background,
            args=(task_id, device_id, suite_info["abs_path"]),
            daemon=True  # 守护线程，Web服务退出时自动结束
        ).start()

        log.info(f"任务{task_id}创建成功（设备：{device_id}，用例：{suite_info['name']}）")
        return jsonify({
            "code": 200,
            "msg": "测试任务已启动",
            "data": {"task_id": task_id}
        })
    except Exception as e:
        error_msg = f"启动测试任务失败：{str(e)}"
        log.error(error_msg, exc_info=True)
        return jsonify({
            "code": 400,
            "msg": error_msg,
            "data": None
        })


@test_bp.get("/status/<task_id>")
def get_task_status(task_id: str):
    """查询测试任务状态接口"""
    try:
        task = test_tasks.get(task_id)
        if not task:
            return jsonify({
                "code": 404,
                "msg": f"任务{task_id}不存在",
                "data": None
            })

        # 补充报告访问URL（若任务成功）
        if "report_path" in task and task["report_path"]:
            task["report_url"] = f"/api/report/files/{task_id}/index.html"

        return jsonify({
            "code": 200,
            "msg": "查询任务状态成功",
            "data": task
        })
    except Exception as e:
        error_msg = f"查询任务{task_id}状态失败：{str(e)}"
        log.error(error_msg)
        return jsonify({
            "code": 400,
            "msg": error_msg,
            "data": None
        })


@test_bp.get("/running")
def get_running_tasks():
    """获取所有运行中任务"""
    try:
        running_tasks = [
            task for task in test_tasks.values()
            if task["status"] == "running"
        ]
        return jsonify({
            "code": 200,
            "msg": f"获取运行中任务成功（共{len(running_tasks)}个）",
            "data": running_tasks
        })
    except Exception as e:
        error_msg = f"获取运行中任务失败：{str(e)}"
        log.error(error_msg)
        return jsonify({
            "code": 400,
            "msg": error_msg,
            "data": []
        })


@test_bp.post("/stop/<task_id>")
def stop_test_task(task_id: str):
    """停止指定测试任务"""
    try:
        task = test_tasks.get(task_id)
        if not task:
            return jsonify({
                "code": 404,
                "msg": f"任务{task_id}不存在",
                "data": None
            })

        if task["status"] != "running":
            return jsonify({
                "code": 400,
                "msg": f"任务{task_id}不在运行中，状态：{task['status']}",
                "data": None
            })

        # 实际项目中需要实现真正的任务停止逻辑
        # 这里只是模拟停止操作
        task["status"] = "stopped"
        task["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task["stop_reason"] = "用户手动停止"

        log.info(f"任务{task_id}已被手动停止")
        return jsonify({
            "code": 200,
            "msg": f"任务{task_id}已停止",
            "data": {"task_id": task_id}
        })
    except Exception as e:
        error_msg = f"停止任务{task_id}失败：{str(e)}"
        log.error(error_msg)
        return jsonify({
            "code": 400,
            "msg": error_msg,
            "data": None
        })


@test_bp.get("/suite/<int:suite_id>")
def get_test_suite(suite_id):
    """获取单个测试用例内容"""
    try:
        suites = get_test_suites()
        if suite_id < 0 or suite_id >= len(suites):
            return jsonify({"code": 404, "msg": f"用例不存在", "data": None})

        suite_info = suites[suite_id]
        with open(suite_info["abs_path"], "r", encoding="utf-8") as f:
            content = f.read()

        return jsonify({
            "code": 200,
            "msg": "获取用例内容成功",
            "data": {
                "id": suite_id,
                "name": suite_info["name"],
                "content": content,
                "abs_path": suite_info["abs_path"],
                "rel_path": suite_info["rel_path"]
            }
        })
    except Exception as e:
        error_msg = f"获取用例内容失败：{str(e)}"
        log.error(error_msg)
        return jsonify({"code": 400, "msg": error_msg, "data": None})


@test_bp.post("/suite")
def create_test_suite():
    """创建新测试用例"""
    try:
        req_data = request.get_json() or {}
        name = req_data.get("name")
        content = req_data.get("content", "")

        if not name or not name.endswith(".py"):
            return jsonify({"code": 400, "msg": "用例名称必须以.py结尾", "data": None})

        test_suite_dir = current_app.config["TEST_SUITE_DIR"]
        file_path = safe_join(test_suite_dir, name)

        if os.path.exists(file_path):
            return jsonify({"code": 400, "msg": "用例已存在", "data": None})

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return jsonify({
            "code": 200,
            "msg": "用例创建成功",
            "data": {"name": name}
        })
    except Exception as e:
        error_msg = f"创建用例失败：{str(e)}"
        log.error(error_msg)
        return jsonify({"code": 400, "msg": error_msg, "data": None})


@test_bp.put("/suite/<int:suite_id>")
def update_test_suite(suite_id):
    """更新测试用例内容"""
    try:
        req_data = request.get_json() or {}
        content = req_data.get("content")

        if content is None:
            return jsonify({"code": 400, "msg": "请提供用例内容", "data": None})

        suites = get_test_suites()
        if suite_id < 0 or suite_id >= len(suites):
            return jsonify({"code": 404, "msg": f"用例不存在", "data": None})

        suite_info = suites[suite_id]
        with open(suite_info["abs_path"], "w", encoding="utf-8") as f:
            f.write(content)

        return jsonify({
            "code": 200,
            "msg": "用例更新成功",
            "data": None
        })
    except Exception as e:
        error_msg = f"更新用例失败：{str(e)}"
        log.error(error_msg)
        return jsonify({"code": 400, "msg": error_msg, "data": None})


@test_bp.delete("/suite/<int:suite_id>")
def delete_test_suite(suite_id):
    """删除测试用例"""
    try:
        suites = get_test_suites()
        if suite_id < 0 or suite_id >= len(suites):
            return jsonify({"code": 404, "msg": f"用例不存在", "data": None})

        suite_info = suites[suite_id]
        os.remove(suite_info["abs_path"])

        return jsonify({
            "code": 200,
            "msg": "用例删除成功",
            "data": None
        })
    except Exception as e:
        error_msg = f"删除用例失败：{str(e)}"
        log.error(error_msg)
        return jsonify({"code": 400, "msg": error_msg, "data": None})
