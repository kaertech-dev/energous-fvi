from datetime import datetime
from app.db import query_one, query_all, get_conn

REQUIRED_STATIONS = (
    "progtest",
    "assembly",
    "lasermarking1",
    "vi",
    "ft1",
    "ft2",
    "lasermarking2",
)
MAX_FAIL_REPETITIONS = 3

def lookup_unit(serial_num: str):
    """Check b2btag_main for the serial and its station statuses."""
    return query_one(
        """
        SELECT serial_num, po_num, progtest, assembly, lasermarking1, vi, ft1, overmold, ft2, lasermarking2, fvi
        FROM energous.esense_main
        WHERE serial_num = %s
        LIMIT 1
        """,
        (serial_num,)
    )

def lookup_prog_id(prog_id: str):
    """Check that the prog_id exists at all in the progtest table."""
    return query_one(
        """
        SELECT prog_id, serial_num
        FROM energous.esense_progtest
        WHERE prog_id = %s
        LIMIT 1
        """,
        (prog_id,)
    )

def verify_prog_matches_serial(prog_id: str, serial_num: str) -> bool:
    """Confirm this specific prog_id is actually tied to this serial_num."""
    row = query_one(
        """
        SELECT prog_id
        FROM energous.esense_progtest
        WHERE prog_id = %s AND serial_num = %s
        LIMIT 1
        """,
        (prog_id, serial_num)
    )
    return row is not None

def already_packed(serial_num: str) -> bool:
    row = query_one(
        "SELECT serial_num FROM energous.esense_fvi WHERE serial_num = %s LIMIT 1",
        (serial_num,)
    )
    return row is not None


def _fail_serials(serial_num: str):
    return tuple(f"{serial_num}_{attempt}" for attempt in range(1, MAX_FAIL_REPETITIONS + 1))


def _failed_attempt_rows(serial_num: str, cursor=None):
    sql = """
        SELECT serial_num
        FROM energous.esense_fvi
        WHERE serial_num IN (%s, %s, %s) AND status = 0
    """
    params = _fail_serials(serial_num)
    if cursor is None:
        return query_all(sql, params)

    cursor.execute(sql + " FOR UPDATE", params)
    return cursor.fetchall()


def _fail_repetition(rows) -> int:
    recorded_repetitions = [
        int(row["serial_num"].rsplit("_", 1)[1])
        for row in rows
    ]
    return max(len(rows), max(recorded_repetitions, default=0))


def fail_repetition(serial_num: str) -> int:
    """Return the number of failed repetitions already recorded for a serial."""
    return _fail_repetition(_failed_attempt_rows(serial_num))


def stations_passed(row: dict) -> bool:
    """Return True if all required stations are recorded as 1."""
    return all(row.get(s) == 1 for s in REQUIRED_STATIONS)


def record_packing(serial_num: str, po_num: str, operator_en: str, shift: str, remarks: str = ""):
    """
    Atomically:
      1. Set fvi=1 in esense_main
      2. Insert a row into esense_fvi (status=1, test_rep=1)
    Used for PASS.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE energous.esense_main
            SET fvi = 1
            WHERE serial_num = %s
            """,
            (serial_num,)
        )

        cur.execute(
            """
            INSERT INTO energous.esense_fvi
                (serial_num, po_num, operator_en, shift, date_time, test_rep, remarks, status)
            VALUES (%s, %s, %s, %s, %s, 1, %s, 1)
            """,
            (serial_num, po_num, operator_en, shift, datetime.now(), remarks)
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_fail(serial_num: str, po_num: str, operator_en: str, shift: str, reason: str):
    """
    Record a FAIL:
      - Inserts into esense_fvi with serial_num suffixed "_1", "_2", or "_3"
      - status = 0, remarks = reason
      - esense_main.fvi is NOT touched (the unit can be reworked and re-scanned).
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT serial_num
            FROM energous.esense_main
            WHERE serial_num = %s
            FOR UPDATE
            """,
            (serial_num,)
        )
        rows = _failed_attempt_rows(serial_num, cur)
        repetition = _fail_repetition(rows) + 1
        if repetition > MAX_FAIL_REPETITIONS:
            conn.rollback()
            return None

        fail_serial = f"{serial_num}_{repetition}"
        cur.execute(
            """
            INSERT INTO energous.esense_fvi
                (serial_num, po_num, operator_en, shift, date_time, test_rep, remarks, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
            """,
            (fail_serial, po_num, operator_en, shift, datetime.now(), repetition, reason)
        )
        conn.commit()
        return repetition
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_prog_check(prog_id: str):
    """
    Step 1: just validate the prog_id exists in progtest.
    """
    prog_id = prog_id.strip()
    prog_row = lookup_prog_id(prog_id)
    if not prog_row:
        return {"status": "not_found", "message": f"Prog ID '{prog_id}' not found in progtest.", "ok": False}

    return {"status": "ok", "message": f"Prog ID '{prog_id}' verified. Now scan the serial number.", "ok": True}


def validate_scan(prog_id: str, serial_num: str):
    """
    Step 2: validate serial against prog_id, stations, already-packed.
    Does NOT record anything — just tells the UI whether it's OK to
    show the PASS / FAIL buttons.
    Returns:
      status : "ok" | "already_packed" | "fail" | "not_found" | "mismatch"
      message: human-readable string
      unit   : the esense_main row (or None)
    """
    serial_num = serial_num.strip()
    prog_id = prog_id.strip()

    if not prog_id:
        return {"status": "fail", "message": "No prog_id was scanned/verified first.", "unit": None}

    unit = lookup_unit(serial_num)
    if not unit:
        return {"status": "not_found", "message": f"Serial '{serial_num}' not found in database.", "unit": None}

    if already_packed(serial_num):
        return {"status": "already_packed", "message": f"Serial '{serial_num}' was already packed.", "unit": unit}

    if fail_repetition(serial_num) >= MAX_FAIL_REPETITIONS:
        return {
            "status": "max_failures",
            "message": f"Serial '{serial_num}' has reached the maximum of {MAX_FAIL_REPETITIONS} FAIL attempts.",
            "unit": unit,
        }

    if not stations_passed(unit):
        failed = [s for s in REQUIRED_STATIONS if unit.get(s) != 1]
        return {
            "status": "fail",
            "message": f"Serial '{serial_num}' has not passed: {', '.join(failed).upper()}.",
            "unit": unit,
        }

    if not verify_prog_matches_serial(prog_id, serial_num):
        return {
            "status": "mismatch",
            "message": f"Prog ID '{prog_id}' does not match serial '{serial_num}'.",
            "unit": unit,
        }

    return {
        "status": "ok",
        "message": f"Serial '{serial_num}' verified. Choose PASS or FAIL.",
        "unit": unit,
    }


def finalize_scan(prog_id: str, serial_num: str, operator_en: str, shift: str, decision: str, remarks: str = ""):
    """
    Step 3: record the operator's decision.
    Re-runs validate_scan first so a stale/tampered client can't force a write.
    decision: "pass" | "fail"
    """
    serial_num = serial_num.strip()
    prog_id = prog_id.strip()
    decision = (decision or "").strip().lower()

    if decision not in ("pass", "fail"):
        return {"status": "fail", "message": "Invalid decision.", "unit": None}

    check = validate_scan(prog_id, serial_num)
    if check["status"] != "ok":
        return check

    unit = check["unit"]

    if decision == "fail":
        reason = remarks.strip()
        if not reason:
            return {"status": "fail", "message": "A fail reason is required.", "unit": unit}
        repetition = record_fail(serial_num, unit["po_num"], operator_en, shift, reason)
        if repetition is None:
            return {
                "status": "max_failures",
                "message": f"Serial '{serial_num}' has reached the maximum of {MAX_FAIL_REPETITIONS} FAIL attempts.",
                "unit": unit,
            }
        return {
            "status": "ok",
            "message": f"Serial '{serial_num}' recorded as FAIL (attempt {repetition} of {MAX_FAIL_REPETITIONS}): {reason}",
            "unit": unit,
            "decision": "fail",
        }

    record_packing(serial_num, unit["po_num"], operator_en, shift, remarks)
    return {
        "status": "ok",
        "message": f"Serial '{serial_num}' packed successfully.",
        "unit": unit,
        "decision": "pass",
    }