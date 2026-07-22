from flask import Blueprint, render_template, jsonify, session, redirect, url_for, request
from app.admin import get_packing_logs, get_operator_summary, get_daily_summary, get_recent_by_operator

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_PASSWORD = "admin1234"  # Change before production or use env var

# ── Admin Auth ────────────────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET"])
def admin_login_page():
    return render_template("admin_login.html")

@admin_bp.route("/login", methods=["POST"])
def admin_login():
    data = request.get_json(force=True)
    if data.get("password") == ADMIN_PASSWORD:
        session["is_admin"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Invalid password."}), 401

@admin_bp.route("/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return jsonify({"ok": True})

def require_admin():
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login_page"))

# ── Admin Pages ───────────────────────────────────────────────────────────────

@admin_bp.route("/")
def dashboard():
    if not session.get("is_admin"):
        return redirect(url_for("admin.admin_login_page"))
    return render_template("admin.html")

# ── Admin API ─────────────────────────────────────────────────────────────────

@admin_bp.route("/api/logs")
def api_logs():
    if not session.get("is_admin"):
        return jsonify({"ok": False}), 401
    limit = int(request.args.get("limit", 200))
    logs = get_packing_logs(limit)
    for row in logs:
        if row.get("date_time"):
            row["date_time"] = row["date_time"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"ok": True, "data": logs})

@admin_bp.route("/api/operator-summary")
def api_operator_summary():
    if not session.get("is_admin"):
        return jsonify({"ok": False}), 401
    rows = get_operator_summary()
    for r in rows:
        if r.get("last_scan"):
            r["last_scan"] = r["last_scan"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"ok": True, "data": rows})

@admin_bp.route("/api/daily-summary")
def api_daily_summary():
    if not session.get("is_admin"):
        return jsonify({"ok": False}), 401
    rows = get_daily_summary()
    for r in rows:
        if r.get("scan_date"):
            r["scan_date"] = str(r["scan_date"])
    return jsonify({"ok": True, "data": rows})

@admin_bp.route("/api/operator/<operator_en>")
def api_operator_detail(operator_en):
    if not session.get("is_admin"):
        return jsonify({"ok": False}), 401
    rows = get_recent_by_operator(operator_en)
    for r in rows:
        if r.get("date_time"):
            r["date_time"] = r["date_time"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"ok": True, "data": rows, "operator_en": operator_en})
