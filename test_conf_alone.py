#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立测试 conf 模块是否能正常导入（排除其他模块干扰）"""
import os
import sys


def main():
    # 1. 配置项目根目录到 sys.path
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
        print(f"[DEBUG] 已添加项目根目录到 sys.path：{PROJECT_ROOT}")

    # 2. 检查 conf 文件夹和文件是否存在
    conf_dir = os.path.join(PROJECT_ROOT, "conf")
    config_yaml = os.path.join(conf_dir, "config.yaml")
    conf_init = os.path.join(conf_dir, "__init__.py")

    print("\n[检查1] conf 相关文件是否存在：")
    print(f"  - conf 文件夹：{'存在' if os.path.exists(conf_dir) else '不存在 ❌'}")
    print(f"  - conf/__init__.py：{'存在' if os.path.exists(conf_init) else '不存在 ❌'}")
    print(f"  - conf/config.yaml：{'存在' if os.path.exists(config_yaml) else '不存在 ❌'}")

    if not os.path.exists(conf_dir) or not os.path.exists(conf_init) or not os.path.exists(config_yaml):
        print("\n[错误] conf 模块缺少必要文件，请先补全！")
        return

    # 3. 尝试独立导入 conf 模块
    try:
        print("\n[检查2] 尝试导入 conf 模块...")
        from conf import GlobalConfig

        print("\n✅ conf 模块导入成功！")
        print("\n[GlobalConfig 关键配置]：")
        print(f"  - 环境：{GlobalConfig['env']}")
        print(f"  - Web 端口：{GlobalConfig['web']['port']}")
        print(f"  - 测试用例目录：{GlobalConfig['path']['test_suite_dir']}")
        print(f"  - 报告目录：{GlobalConfig['path']['report_root_dir']}")

    except ImportError as e:
        print(f"\n❌ 导入 conf 模块失败（ImportError）：{str(e)}")
        print("\n[可能原因]：")
        print("  1. 项目根目录未加入 sys.path（已自动添加，可忽略）")
        print("  2. conf/__init__.py 文件名错误（必须是 __init__.py，注意下划线）")
        print("  3. conf/__init__.py 内部代码错误（如下方堆栈）")
        import traceback
        traceback.print_exc()

    except Exception as e:
        print(f"\n❌ conf 模块初始化失败（其他错误）：{str(e)}")
        print("\n[可能原因]：")
        print("  1. config.yaml 格式错误（缩进、特殊字符）")
        print("  2. util.yaml_util 模块缺失或错误")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
