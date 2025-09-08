# @Time     : 2024/5/20 15:00
# @Author   : CN-LanBao
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, send_from_directory, abort
from app.routes.test import test_tasks
from util.path_util import safe_join

report_bp = Blueprint("report", __name__)


@report_bp.get("/<task_id>")
def get_report_info(task_id: str):
    """获取报告基本信息（含访问URL）"""
    task = test_tasks.get(task_id)
    if not task or "report_path" not in task:
        return jsonify({
            "code": 404,
            "msg": f"任务{task_id}报告不存在（任务未完成或执行失败）",
            "data": None
        })

    return jsonify({
        "code": 200,
        "msg": "获取报告信息成功",
        "data": {
            "task_id": task_id,
            "report_path": task["report_path"],
            "log_path": task.get("log_path"),
            "access_url": f"/api/report/files/{task_id}/index.html",
            "pytest_returncode": task.get("pytest_returncode")
        }
    })


@report_bp.get("/files/<task_id>/<path:filename>")
def get_report_file(task_id: str, filename: str):
    """获取报告静态文件（HTML/CSS/JS/图片）"""
    # 1. 校验任务和报告目录
    task = test_tasks.get(task_id)
    if not task or "report_path" not in task:
        abort(404, description=f"任务{task_id}报告不存在")

    report_dir = task["report_path"]

    # 2. 安全拼接路径（防止路径穿越）
    try:
        file_path = safe_join(report_dir, filename)
    except ValueError:
        abort(403, description="非法文件访问（路径穿越）")

    # 3. 校验文件存在性
    if not file_path or not os.path.exists(file_path):
        abort(404, description=f"报告文件不存在：{filename}")

    # 4. 返回文件（支持所有静态资源）
    return send_from_directory(report_dir, filename, as_attachment=False)