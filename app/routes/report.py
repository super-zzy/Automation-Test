# @Time     : 2024/1/1 10:20
# @Author   : CN-LanBao
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, send_from_directory, abort
import os
from app.routes.test import test_tasks  # 导入任务状态，获取静态报告目录

report_bp = Blueprint('report', __name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_RESULT_FOLDER = os.path.join(BASE_DIR, "result")


@report_bp.get('/<task_id>')
def get_report(task_id):
    """获取报告信息（返回静态HTML报告的访问URL）"""
    # 从任务状态中获取静态报告目录（allure_html）
    task = test_tasks.get(task_id)
    if not task or not task.get("allure_html_dir"):
        return jsonify({"code": 400, "msg": "报告不存在（任务未完成或目录错误）"})

    allure_html_dir = task["allure_html_dir"]
    if not os.path.exists(allure_html_dir):
        return jsonify({"code": 400, "msg": "静态报告目录不存在"})

    return jsonify({
        "code": 200,
        "msg": "成功",
        "data": {
            "allure_html_dir": allure_html_dir,
            "access_url": f"/api/report/files/{task_id}/index.html"  # 访问静态报告的URL
        }
    })


@report_bp.get('/files/<task_id>/<path:filename>')
def get_report_file(task_id, filename):
    """核心接口：返回静态报告文件（从 allure_html 目录读取）"""
    # 1. 从任务状态中获取当前任务的静态报告目录
    task = test_tasks.get(task_id)
    if not task or not task.get("allure_html_dir"):
        abort(404, description="任务不存在或报告未生成")

    allure_html_dir = task["allure_html_dir"]
    # 2. 校验文件是否存在（避免路径穿越攻击）
    file_path = os.path.join(allure_html_dir, filename)
    # 安全校验：确保请求的文件在 allure_html_dir 目录内（防止路径穿越）
    if not os.path.abspath(file_path).startswith(os.path.abspath(allure_html_dir)):
        abort(403, description="非法文件访问")
    if not os.path.exists(file_path):
        abort(404, description=f"文件不存在：{filename}")

    # 3. 返回文件（支持所有静态资源：HTML/CSS/JS/图片）
    return send_from_directory(allure_html_dir, filename, as_attachment=False)
