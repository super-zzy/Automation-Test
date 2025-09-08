from flask import Flask
import os
from flask import send_from_directory, jsonify  # 保留静态资源相关导入


# ------------------- 关键1：先创建 app 对象，不提前导入 test_bp -------------------
def create_app():
    app = Flask(__name__)

    # 配置报告静态资源访问（原逻辑保留，移到 create_app 内部）
    BASE_DIR = "D:\\PyCharmProjects\\ums_uiautomator"
    REPORT_ROOT_DIR = os.path.join(BASE_DIR, "result")

    @app.route('/api/report/files/<task_id>/static/<path:filename>')
    def serve_report_static(task_id, filename):
        static_dir = os.path.join(REPORT_ROOT_DIR, task_id, "allure_html", "static")
        if not os.path.exists(static_dir):
            return jsonify({"code": 404, "msg": f"静态资源目录不存在：{static_dir}"}), 404
        return send_from_directory(static_dir, filename)

    # ------------------- 关键2：在 app 创建后，再导入并注册 test_bp（打破循环） -------------------
    # 原因：此时 app 对象已创建，test.py 再导入 app 时不会触发二次初始化
    from app.routes.test import test_bp
    app.register_blueprint(test_bp)

    # 初始化 scheduler（若使用 APScheduler，确保在 app 内初始化）
    from flask_apscheduler import APScheduler
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()

    # 将 scheduler 绑定到 app 上，供其他模块通过 current_app 访问（避免直接导入）
    app.config['SCHEDULER'] = scheduler

    return app
