from . import create_app

app = create_app()


if __name__ == "__main__":
    # 仅用于本地开发调试，生产环境建议使用 gunicorn 等 WSGI 容器。
    app.run(host="0.0.0.0", port=5000)



