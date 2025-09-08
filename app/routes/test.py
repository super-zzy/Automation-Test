import traceback
import os
import subprocess
import uuid
# 关键修复：从 flask.helpers 导入 safe_join（兼容 Flask 1.x 和 2.x）
from flask import Blueprint, jsonify, request, send_file, current_app
from flask.helpers import safe_join  # 单独导入 safe_join，避免版本兼容问题
from util.log_util import LogUtil
from datetime import datetime
from threading import Thread
import shutil

# ------------------- 1. 初始化蓝图（无任何app直接导入） -------------------
test_bp = Blueprint('test', __name__)
test_tasks = {}  # 全局任务状态存储（task_id: 任务信息）


# ------------------- 2. 工具函数 -------------------
def is_valid_path(path):
    """校验路径是否有效"""
    if path is None:
        return False
    if isinstance(path, (str, os.PathLike)):
        return bool(str(path).strip())
    return False


class TempLog:
    """临时日志类（LogUtil初始化失败时降级使用）"""

    @staticmethod
    def info(msg):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] {msg}")

    @staticmethod
    def warning(msg):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [WARNING] {msg}")

    @staticmethod
    def error(msg):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] {msg}")


def get_task_id():
    """生成唯一任务ID（毫秒级时间戳+4位随机字符串）"""
    time_part = datetime.now().strftime("%Y%m%d%H%M%S%f")[:13]  # 毫秒级时间戳
    random_part = str(uuid.uuid4()).replace("-", "")[:4]  # 4位随机字符串
    return f"{time_part}_{random_part}"


def get_test_suites():
    """获取测试用例列表（从配置的TEST_SUITE_DIR中读取）"""
    suites = []
    log_util = None
    try:
        # 从current_app获取配置（避免硬编码）
        test_suite_dir = current_app.config['TEST_SUITE_DIR']
        temp_task_id = get_task_id()
        log_util = LogUtil(
            device_id="debug_device",
            task_id=temp_task_id,
            logger_name="get_test_suites"
        )
        log_util.info(f"开始获取测试用例，目录：{test_suite_dir}")

        # 校验用例目录
        if not is_valid_path(test_suite_dir):
            raise ValueError(f"测试用例目录无效：{test_suite_dir}")
        if not os.path.exists(test_suite_dir):
            log_util.warning(f"用例目录不存在，自动创建：{test_suite_dir}")
            os.makedirs(test_suite_dir, exist_ok=True)

        # 遍历目录，筛选.py用例（排除conftest.py）
        for root, _, files in os.walk(test_suite_dir):
            if not is_valid_path(root):
                log_util.error(f"跳过无效目录：{root}")
                continue
            for name in files:
                if isinstance(name, str) and name.endswith(".py") and name != "conftest.py":
                    case_abs_path = os.path.abspath(os.path.join(root, name))
                    case_rel_path = os.path.relpath(case_abs_path, test_suite_dir)
                    suites.append({
                        "id": len(suites),
                        "name": name,
                        "abs_path": case_abs_path,
                        "rel_path": case_rel_path
                    })
        log_util.info(f"获取用例完成，共 {len(suites)} 个可用用例")
        return suites
    except Exception as e:
        if log_util:
            log_util.error(f"获取用例失败：{str(e)}")
            log_util.error(f"堆栈：\n{traceback.format_exc()}")
        else:
            TempLog.error(f"获取用例失败：{str(e)}")
        return []


# ------------------- 3. 完整run_test方法（包含所有逻辑） -------------------
def run_test(task_id, device_id, suite_abs_path):
    """
    执行测试任务的完整逻辑
    :param task_id: 任务ID
    :param device_id: 设备ID
    :param suite_abs_path: 测试用例绝对路径
    """
    # 初始化日志和上下文
    log_util = None
    try:
        # 1. 进入Flask上下文（用current_app替代直接导入的app）
        with current_app.app_context():
            log_util = LogUtil(
                device_id=device_id,
                task_id=task_id,
                logger_name=f"run_test_{task_id}"
            )
            log_util.info(f"=== 任务 {task_id} 开始执行 ===")
            log_util.info(f"设备ID：{device_id}，用例路径：{suite_abs_path}")

            # 2. 从current_app获取配置（避免硬编码）
            report_root_dir = current_app.config['REPORT_ROOT_DIR']
            task_report_dir = os.path.join(report_root_dir, task_id)  # 任务专属报告目录
            allure_raw_dir = os.path.join(task_report_dir, "allure_raw")  # 原始报告数据
            allure_html_dir = os.path.join(task_report_dir, "allure_html")  # HTML报告
            log_file_path = os.path.join(task_report_dir, f"task_{task_id}.log")  # 任务日志

            # 3. 初始化目录（清理旧报告，创建新目录）
            log_util.info(f"初始化任务目录：{task_report_dir}")
            if os.path.exists(task_report_dir):
                shutil.rmtree(task_report_dir)  # 清理旧报告
            os.makedirs(allure_raw_dir, exist_ok=True)
            os.makedirs(allure_html_dir, exist_ok=True)

            # 4. 校验用例路径有效性
            if not os.path.exists(suite_abs_path):
                raise FileNotFoundError(f"测试用例不存在：{suite_abs_path}")
            if not os.path.isfile(suite_abs_path):
                raise ValueError(f"{suite_abs_path} 不是有效文件")

            # 5. 执行pytest（生成allure原始报告）
            log_util.info("开始执行pytest测试...")
            pytest_cmd = [
                "python", "-m", "pytest",
                suite_abs_path,
                f"--alluredir={allure_raw_dir}",  # 输出原始报告到allure_raw
                "-v",  # 详细日志
                "--tb=short"  # 精简异常堆栈
            ]
            # 执行命令并捕获输出
            pytest_result = subprocess.run(
                pytest_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=3600  # 超时时间1小时
            )

            # 6. 保存pytest执行日志到文件
            with open(log_file_path, "w", encoding="utf-8") as f:
                f.write(f"=== pytest 执行日志（任务 {task_id}）===\n")
                f.write(f"执行命令：{' '.join(pytest_cmd)}\n")
                f.write(f"返回码：{pytest_result.returncode}\n")
                f.write(f"\n=== 标准输出（stdout）===\n{pytest_result.stdout}\n")
                f.write(f"\n=== 错误输出（stderr）===\n{pytest_result.stderr}\n")
            log_util.info(f"pytest日志已保存到：{log_file_path}")

            # 7. 生成HTML报告（调用allure命令）
            log_util.info("开始生成HTML报告...")
            allure_cmd = [
                "allure", "generate",
                allure_raw_dir,
                "-o", allure_html_dir,  # 输出HTML报告到allure_html
                "--clean"  # 覆盖现有报告（避免残留）
            ]
            allure_result = subprocess.run(
                allure_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8"
            )

            # 8. 校验报告生成结果
            if allure_result.returncode != 0:
                raise Exception(f"allure报告生成失败：{allure_result.stderr[:500]}")
            index_html_path = os.path.join(allure_html_dir, "index.html")
            if not os.path.exists(index_html_path):
                raise FileNotFoundError(f"报告文件不存在：{index_html_path}")
            log_util.info(f"HTML报告生成成功：{index_html_path}")

            # 9. 更新任务状态（成功）
            test_tasks[task_id].update({
                "status": "success",
                "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "report_path": allure_html_dir,
                "log_path": log_file_path,
                "pytest_returncode": pytest_result.returncode
            })
            log_util.info(f"=== 任务 {task_id} 执行成功 ===")

    # 10. 异常处理（捕获所有错误，更新任务状态）
    except subprocess.TimeoutExpired:
        error_msg = f"任务执行超时（超过1小时）"
        if log_util:
            log_util.error(error_msg)
        test_tasks[task_id].update({
            "status": f"failed: {error_msg}",
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_msg": error_msg
        })
    except Exception as e:
        error_msg = str(e)[:500]  # 限制错误信息长度
        if log_util:
            log_util.error(f"任务执行失败：{error_msg}")
            log_util.error(f"异常堆栈：\n{traceback.format_exc()}")
        else:
            TempLog.error(f"任务 {task_id} 执行失败：{error_msg}")
        # 更新任务状态（失败）
        test_tasks[task_id].update({
            "status": f"failed: {error_msg}",
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_msg": error_msg
        })


# ------------------- 4. 接口定义 -------------------
@test_bp.get('/api/test/suites')
def get_test_suite_list():
    """获取测试用例列表接口"""
    log_util = TempLog()
    try:
        log_util.info("收到 /api/test/suites 请求")
        suites = get_test_suites()
        return jsonify({
            "code": 200,
            "msg": f"获取用例成功（共 {len(suites)} 个）",
            "data": suites
        })
    except Exception as e:
        error_msg = f"获取用例列表失败：{str(e)}"
        log_util.error(error_msg)
        return jsonify({
            "code": 400,
            "msg": error_msg,
            "data": []
        })


@test_bp.post('/api/test/start')
def start_test():
    """启动测试任务接口"""
    log_util = TempLog()
    try:
        log_util.info("收到 /api/test/start 请求")
        # 获取请求参数
        request_data = request.json or {}
        device_id = request_data.get("device_id")
        suite_id = request_data.get("suite_id")

        # 1. 校验参数
        if not device_id or not str(device_id).strip():
            raise ValueError("设备ID（device_id）不能为空")
        if suite_id is None:
            raise ValueError("测试用例ID（suite_id）不能为空")

        # 2. 获取选中的用例路径
        suites = get_test_suites()
        try:
            suite_id = int(suite_id)
            if suite_id < 0 or suite_id >= len(suites):
                raise IndexError(f"用例ID {suite_id} 超出范围（共 {len(suites)} 个用例）")
            selected_suite = suites[suite_id]
            suite_abs_path = selected_suite["abs_path"]
        except (ValueError, IndexError) as e:
            raise ValueError(f"用例ID无效：{str(e)}")

        # 3. 生成任务ID并初始化状态
        task_id = get_task_id()
        test_tasks[task_id] = {
            "task_id": task_id,
            "device_id": device_id,
            "suite_name": selected_suite["name"],
            "suite_path": suite_abs_path,
            "status": "running",  # pending→running
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": None,
            "error_msg": None
        }
        log_util.info(f"初始化任务状态：{test_tasks[task_id]}")

        # 4. 异步启动测试（避免阻塞接口）
        Thread(
            target=run_test,
            args=(task_id, device_id, suite_abs_path),
            daemon=True  # 守护线程：主进程退出时自动结束
        ).start()

        # 5. 返回响应
        return jsonify({
            "code": 200,
            "msg": "测试任务已启动",
            "data": {
                "task_id": task_id,
                "status": "running",
                "start_time": test_tasks[task_id]["start_time"],
                "suite_name": selected_suite["name"]
            }
        })
    except Exception as e:
        error_msg = f"启动测试失败：{str(e)}"
        log_util.error(error_msg)
        return jsonify({
            "code": 400,
            "msg": error_msg,
            "data": {}
        })


@test_bp.get('/api/report/files/<task_id>/index.html')
def get_report_index(task_id):
    """获取测试报告index.html接口"""
    log_util = TempLog()
    try:
        # 1. 校验task_id
        if not task_id or not str(task_id).strip():
            raise ValueError("任务ID（task_id）不能为空")
        if task_id not in test_tasks:
            raise ValueError(f"任务 {task_id} 不存在")

        # 2. 从current_app获取报告根目录
        report_root_dir = current_app.config['REPORT_ROOT_DIR']
        # 拼接报告路径（与run_test中一致）
        allure_html_dir = os.path.join(report_root_dir, task_id, "allure_html")
        index_html_path = safe_join(allure_html_dir, "index.html")  # 安全路径拼接（防遍历）

        # 3. 校验文件存在性
        log_util.info(f"查找报告文件：{index_html_path}")
        if not os.path.exists(index_html_path):
            raise FileNotFoundError(f"报告文件不存在：{index_html_path}（可能任务未执行完）")
        if not os.path.isfile(index_html_path):
            raise ValueError(f"{index_html_path} 不是有效文件")

        # 4. 返回报告文件（浏览器中打开）
        log_util.info(f"成功返回报告：{index_html_path}")
        return send_file(
            index_html_path,
            mimetype="text/html",
            as_attachment=False
        )
    except Exception as e:
        error_msg = f"获取报告失败：{str(e)}"
        log_util.error(error_msg)
        return jsonify({
            "code": 404 if "不存在" in error_msg else 400,
            "msg": error_msg,
            "data": {}
        })


@test_bp.get('/api/test/task/<task_id>')
def get_task_status(task_id):
    """获取任务状态接口（辅助接口）"""
    if not task_id or task_id not in test_tasks:
        return jsonify({
            "code": 404,
            "msg": f"任务 {task_id} 不存在",
            "data": {}
        })
    return jsonify({
        "code": 200,
        "msg": "获取任务状态成功",
        "data": test_tasks[task_id]
    })
