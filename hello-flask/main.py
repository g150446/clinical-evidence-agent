import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "Hello World from Cloud Run macbook"

if __name__ == "__main__":
    # Cloud Runはポート8080、ホスト0.0.0.0でリッスンする必要があります
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
