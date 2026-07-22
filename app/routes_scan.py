from flask import Blueprint, request, jsonify, session, render_template
from app.auth import authenticate_operator
from app.scan import process_scan
from app.config import Config

scan_bp = Blueprint("scan", __name__)

# ── Auth ──────────────────────────────────────────────────────────────────────

@scan_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@scan_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    employee_num = (data.get("employee_num") or "").strip()
    if not employee_num:
        return jsonify({"ok": False, "message": "Employee number is required."}), 400

    operator = authenticate_operator(employee_num)
    if not operator:
        return jsonify({"ok": False, "message": "Employee number not found."}), 401

    session["operator_en"] = operator["operator_en"]
    session["employee_num"] = employee_num
    return jsonify({"ok": True, "operator_en": operator["operator_en"]})

@scan_bp.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

# ── Scan UI ───────────────────────────────────────────────────────────────────

@scan_bp.route("/")
def index():
    if "operator_en" not in session:
        from flask import redirect, url_for
        return redirect(url_for("scan.login_page"))
    return render_template("scan.html",
                           operator_en=session["operator_en"],
                           tray_limit=Config.TRAY_LIMIT)

# ── Scan API ──────────────────────────────────────────────────────────────────

@scan_bp.route("/api/scan", methods=["POST"])
def api_scan():
    if "operator_en" not in session:
        return jsonify({"ok": False, "message": "Not authenticated."}), 401

    data = request.get_json(force=True)
    serial_num = (data.get("serial_num") or "").strip()
    shift      = (data.get("shift") or "").strip()
    remarks    = (data.get("remarks") or "").strip()

    if not serial_num:
        return jsonify({"ok": False, "message": "Serial number is required."}), 400

    result = process_scan(
        serial_num=serial_num,
        operator_en=session["operator_en"],
        shift=shift,
        remarks=remarks,
    )

    ok = result["status"] == "ok"
    return jsonify({"ok": ok, **result})
