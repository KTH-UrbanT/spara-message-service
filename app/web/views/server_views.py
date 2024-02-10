import os
from flask import Blueprint, send_from_directory, current_app

bp = Blueprint(
    "server",
    __name__,
)

@bp.route("/")
def index():
    return "SPARA server is running"

@bp.route("/<path:path>")
def catch_all(path):
    if path != "" and os.path.exists(os.path.join(current_app.static_folder, path)):
        return send_from_directory(current_app.static_folder, path)
    else:
        return send_from_directory(current_app.static_folder, "index.html")
