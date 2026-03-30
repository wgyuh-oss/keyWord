import os

from flask import Flask, Response, jsonify, render_template, request, send_from_directory, stream_with_context

from config import has_config, load_config, save_config
from services.discovery import EXPORTS_DIR, discover_keywords

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config/status")
def config_status():
    return jsonify({"configured": has_config()})


@app.route("/api/config", methods=["POST"])
def save_api_config():
    data = request.json
    try:
        save_config(data)
        return jsonify({"success": True, "message": "API 키가 저장되었습니다."})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400


@app.route("/api/discover")
def start_discovery():
    seed = request.args.get("seed", "").strip()
    try:
        target = int(request.args.get("count", "200"))
    except ValueError:
        target = 200

    if not seed:
        return jsonify({"error": "키워드를 입력해주세요."}), 400

    config = load_config()
    if not config:
        return jsonify({"error": "API 키를 먼저 설정해주세요."}), 400

    target = max(10, min(target, 50000))

    def generate():
        yield from discover_keywords(seed, target, config)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/download/<filename>")
def download_csv(filename):
    return send_from_directory(EXPORTS_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    app.run(debug=True, port=5000, threaded=True)
