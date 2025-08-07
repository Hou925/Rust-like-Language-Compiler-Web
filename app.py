from flask import Flask
from routes import index, analyze

app = Flask(__name__)

# 注册路由
app.add_url_rule("/", view_func=index)
app.add_url_rule("/analyze", view_func=analyze, methods=["POST"])

if __name__ == "__main__":
    app.run(debug=True)