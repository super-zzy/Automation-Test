from app import create_app  # 导入 create_app 函数，而非直接导入 app

# ------------------- 关键：通过 create_app 函数创建 app 对象，避免循环导入 -------------------
app = create_app()

if __name__ == "__main__":
    # 启动 Flask 服务（保持原配置，如端口、debug 模式）
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True  # 生产环境需改为 False
    )