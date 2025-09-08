# @Time     : 2024/1/1 10:05
# @Author   : CN-LanBao
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify
import subprocess

device_bp = Blueprint('device', __name__)

def get_device():
    """复用原逻辑：获取adb连接设备"""
    cmd = "adb devices | findstr /E device"  # Windows命令，Linux/macOS替换为"adb devices | grep device$"
    run_out = subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True
    ).stdout.splitlines()
    # 格式：[{id: 0, device_id: "123456"}, ...]
    return [{"id": idx, "device_id": info.split()[0]} for idx, info in enumerate(run_out)]

@device_bp.get('/list')
def get_device_list():
    """API：获取设备列表"""
    devices = get_device()
    if not devices:
        return jsonify({"code": 400, "msg": "未检测到adb连接设备", "data": []})
    return jsonify({"code": 200, "msg": "成功", "data": devices})