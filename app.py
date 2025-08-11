from flask import Flask
from routes import index, analyze, download_ir, download_asm

app = Flask(__name__)

# 注册路由
app.add_url_rule("/", view_func=index)
app.add_url_rule("/analyze", view_func=analyze, methods=["POST"])
app.add_url_rule("/download_ir", view_func=download_ir, methods=["POST"])
app.add_url_rule("/download_asm", view_func=download_asm, methods=["POST"])

if __name__ == "__main__":
    app.run(debug=True)