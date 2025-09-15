# @Time     : 2025/9/15 18:00
# @Author   : zyli3
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify
from core.device_manager import DeviceManager
from util.log_util import TempLog

device_bp = Blueprint("device", __name__)
log = TempLog()


@device_bp.get("/list")
def get_device_list():
    """获取在线设备列表接口"""
    try:
        log.info("收到设备列表查询请求")
        devices = DeviceManager.get_device_list()
        return jsonify({
            "code": 200,
            "msg": f"获取在线设备{len(devices)}个",
            "data": devices
        })
    except Exception as e:
        error_msg = f"获取设备列表失败：{str(e)}"
        log.error(error_msg)
        return jsonify({
            "code": 400,
            "msg": error_msg,
            "data": []
        })


@device_bp.get("/<device_id>/status")
def get_device_status(device_id: str):
    """获取指定设备状态接口"""
    try:
        log.info(f"收到设备{device_id}状态查询请求")
        devices = DeviceManager.get_device_list()
        target_device = next((d for d in devices if d["device_id"] == device_id), None)

        if not target_device:
            return jsonify({
                "code": 404,
                "msg": f"设备{device_id}未在线或不存在",
                "data": None
            })

        return jsonify({
            "code": 200,
            "msg": "获取设备状态成功",
            "data": target_device
        })
    except Exception as e:
        error_msg = f"获取设备{device_id}状态失败：{str(e)}"
        log.error(error_msg)
        return jsonify({
            "code": 400,
            "msg": error_msg,
            "data": None
        })