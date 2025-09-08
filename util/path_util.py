# @Time     : 2024/5/20 10:10
# @Author   : CN-LanBao
# -*- coding: utf-8 -*-
import os


def safe_join(base_dir: str, *paths: str) -> str:
    """
    安全拼接路径（防止路径穿越攻击）
    :param base_dir: 基础目录（限制所有路径在此目录下）
    :param paths: 待拼接的子路径
    :return: 安全的绝对路径
    :raises ValueError: 路径超出基础目录范围
    """
    base_abs = os.path.abspath(base_dir)
    target_path = os.path.abspath(os.path.join(base_abs, *paths))

    # 校验目标路径是否在基础目录内
    if not target_path.startswith(base_abs):
        raise ValueError(f"非法路径：{os.path.join(*paths)}（超出基础目录{base_dir}）")
    return target_path


def ensure_dir_exists(dir_path: str) -> None:
    """确保目录存在，不存在则创建"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)