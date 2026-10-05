from flask import Blueprint, request, jsonify, session, render_template
from app.auth import authenticate_operator
from app.config import Config
from app.scan import process_prog_check, finalize_scan, validate_scan

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
        attempts = session.get("login_attempt", 0) + 1
        session["login_attempt"] = attempts
        if attempts >=3:
            return jsonify({
                "ok": False, "message": "ang kulit mo, MALI NGANII!"
            }), 401
        elif attempts >=6:
            return jsonify({
                            "ok": False, "message": "Inulit pa talaga nya!"
                        }), 401
        return jsonify({"ok": False, "message": "Employee number not found.!!"}), 401

    session["login_attempt"] = 0
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

# ── Prog ID check (step 1) ───────────────────────────────────────────────────

@scan_bp.route("/api/check-prog", methods=["POST"])
def api_check_prog():
    if "operator_en" not in session:
        return jsonify({"ok": False, "message": "Not authenticated."}), 401

    data = request.get_json(force=True)
    prog_id = (data.get("prog_id") or "").strip()

    if not prog_id:
        return jsonify({"ok": False, "message": "Prog ID is required."}), 400

    result = process_prog_check(prog_id)
    return jsonify(result)

# ── Serial validation (step 2) ───────────────────────────────────────────────

@scan_bp.route("/api/scan", methods=["POST"])
def api_scan():
    if "operator_en" not in session:
        return jsonify({"ok": False, "message": "Not authenticated."}), 401

    data = request.get_json(force=True)
    prog_id    = (data.get("prog_id") or "").strip()
    serial_num = (data.get("serial_num") or "").strip()

    if not prog_id:
        return jsonify({"ok": False, "message": "Prog ID must be verified first."}), 400
    if not serial_num:
        return jsonify({"ok": False, "message": "Serial number is required."}), 400

    result = validate_scan(prog_id, serial_num)
    ok = result["status"] == "ok"
    return jsonify({"ok": ok, **result})

# ── Pass / Fail decision (step 3) ────────────────────────────────────────────

@scan_bp.route("/api/scan-decision", methods=["POST"])
def api_scan_decision():
    if "operator_en" not in session:
        return jsonify({"ok": False, "message": "Not authenticated."}), 401

    data = request.get_json(force=True)
    prog_id    = (data.get("prog_id") or "").strip()
    serial_num = (data.get("serial_num") or "").strip()
    decision   = (data.get("decision") or "").strip().lower()
    shift      = (data.get("shift") or "").strip()
    remarks    = (data.get("remarks") or "").strip()

    if not prog_id or not serial_num:
        return jsonify({"ok": False, "message": "Prog ID and serial number are required."}), 400
    if decision not in ("pass", "fail"):
        return jsonify({"ok": False, "message": "Decision must be 'pass' or 'fail'."}), 400
    if decision == "fail" and not remarks:
        return jsonify({"ok": False, "message": "Please enter a fail reason."}), 400

    result = finalize_scan(
        prog_id=prog_id,
        serial_num=serial_num,
        operator_en=session["operator_en"],
        shift=shift,
        decision=decision,
        remarks=remarks,
    )

    ok = result["status"] == "ok"
    return jsonify({"ok": ok, **result})