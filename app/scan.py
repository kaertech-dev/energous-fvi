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

def already_packed(serial_num: str) -> dict | None:
    return query_one(
        """
        SELECT serial_num, po_num, operator_en, shift, date_time, test_rep, remarks, status
        FROM energous.esense_fvi
        WHERE serial_num = %s AND status = 1
        LIMIT 1
        """,
        (serial_num,)
    )

def _failed_attempt_rows(serial_num: str, cursor=None):
    sql = """
        SELECT serial_num, remarks
        FROM energous.esense_fvi
        WHERE serial_num LIKE %s ESCAPE '=' AND status = 0
    """
    escaped_serial = (
        serial_num.replace("=", "==")
        .replace("%", "=%")
        .replace("_", "=_")
    )
    params = (f"{escaped_serial}=_%",)
    if cursor is None:
        return query_all(sql, params)

    cursor.execute(sql + " FOR UPDATE", params)
    return cursor.fetchall()

def _fail_repetition(rows) -> int:
    recorded_repetitions = [
        int(row["serial_num"].rsplit("_", 1)[1])
        for row in rows
        if row["serial_num"].rsplit("_", 1)[1].isdigit()
    ]
    return max(recorded_repetitions, default=0)

def _fail_count(serial_num: str, rows=None) -> int:
    """Count operator-recorded FAILs, excluding prog ID mismatch records."""
    if rows is None:
        rows = _failed_attempt_rows(serial_num)
    return sum(
        not (row.get("remarks") or "").startswith("PROG ID MISMATCH:")
        for row in rows
    )

def stations_passed(row: dict) -> bool:
    """Return True if all required stations are recorded as 1."""
    return all(row.get(s) == 1 for s in REQUIRED_STATIONS)

def _already_packed_message(record: dict) -> str:
    recorded_at = record["date_time"]
    if isinstance(recorded_at, datetime):
        recorded_at = recorded_at.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"Serial '{record['serial_num']}' already has a saved PASS row "
        f"(PO {record['po_num']}, operator {record['operator_en']}, "
        f"shift {record['shift']}, recorded at {recorded_at}). "
        "No duplicate was written."
    )

def record_packing(
    serial_num: str,
    po_num: str,
    operator_en: str,
    shift: str,
    remarks: str = "",
) -> dict | None:
    """
    Atomically:
      1. Lock the unit row and check for an existing PASS record.
      2. Set fvi=1 and insert a PASS row if none exists.
    Returns an existing PASS row if this is a repeated request.
    """
    conn = get_conn(read_timeout=15)
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
        cur.execute(
            """
            SELECT serial_num, po_num, operator_en, shift, date_time, test_rep, remarks, status
            FROM energous.esense_fvi
            WHERE serial_num = %s AND status = 1
            LIMIT 1
            FOR UPDATE
            """,
            (serial_num,)
        )
        existing_record = cur.fetchone()
        if existing_record:
            conn.commit()
            return existing_record

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
        return None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_fail(serial_num: str, po_num: str, operator_en: str, shift: str, reason: str):
    """
    Record a FAIL using the shared serial/test repetition sequence.
    Only operator-recorded FAILs count toward the three-attempt limit.
    """
    conn = get_conn(read_timeout=15)
    try:
        if reason.startswith("PROG ID MISMATCH:"):
            reason = f"FAIL REASON: {reason}"
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
        if _fail_count(serial_num, rows) >= MAX_FAIL_REPETITIONS:
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


def record_prog_mismatch(
    prog_id: str,
    serial_num: str,
    po_num: str,
    operator_en: str,
    shift: str,
) -> dict:
    expected_prog_ids = [
        row["prog_id"]
        for row in query_all(
            """
            SELECT DISTINCT prog_id
            FROM energous.esense_progtest
            WHERE serial_num = %s
            ORDER BY prog_id
            """,
            (serial_num,),
        )
    ]
    expected = ", ".join(map(str, expected_prog_ids)) if expected_prog_ids else "none found"
    remarks = (
        f"PROG ID MISMATCH: scanned prog_id={prog_id}; "
        f"expected prog_id={expected}."
    )

    conn = get_conn(read_timeout=15)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT serial_num
            FROM energous.esense_main
            WHERE serial_num = %s
            FOR UPDATE
            """,
            (serial_num,),
        )
        repetition = _fail_repetition(_failed_attempt_rows(serial_num, cur)) + 1
        mismatch_serial = f"{serial_num}_{repetition}"
        cur.execute(
            """
            INSERT INTO energous.esense_fvi
                (serial_num, po_num, operator_en, shift, date_time, test_rep, remarks, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
            """,
            (
                mismatch_serial,
                po_num,
                operator_en,
                shift,
                datetime.now(),
                repetition,
                remarks,
            ),
        )
        conn.commit()
        return {
            "serial_num": mismatch_serial,
            "test_rep": repetition,
            "remarks": remarks,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_prog_check(prog_id: str):
    """
    Look up the serial number associated with a prog_id.
    """
    prog_id = prog_id.strip()
    prog_row = lookup_prog_id(prog_id)
    if not prog_row:
        return {"status": "not_found", "message": f"Prog ID '{prog_id}' not found in progtest.", "ok": False}

    serial_num = (prog_row.get("serial_num") or "").strip()
    if not serial_num:
        return {
            "status": "not_found",
            "message": f"No serial number is associated with prog ID '{prog_id}'.",
            "ok": False,
        }

    return {
        "status": "ok",
        "message": f"Prog ID '{prog_id}' verified. Serial '{serial_num}' retrieved.",
        "ok": True,
        "serial_num": serial_num,
    }


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

    packed_record = already_packed(serial_num)
    if packed_record:
        return {
            "status": "already_packed",
            "message": _already_packed_message(packed_record),
            "unit": unit,
        }

    prog_mismatch = not verify_prog_matches_serial(prog_id, serial_num)
    if prog_mismatch:
        return {
            "status": "mismatch",
            "message": f"Prog ID '{prog_id}' does not match serial '{serial_num}'.",
            "unit": unit,
        }

    if _fail_count(serial_num) >= MAX_FAIL_REPETITIONS:
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

    return {
        "status": "ok",
        "message": f"Serial '{serial_num}' verified. Choose PASS or FAIL.",
        "unit": unit,
    }


def finalize_scan(
    prog_id: str,
    serial_num: str,
    operator_en: str,
    shift: str,
    decision: str,
    remarks: str = "",
):
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
        if decision == "pass" and check["status"] == "already_packed":
            return {
                "status": "ok",
                "message": check["message"],
                "unit": check["unit"],
                "decision": "pass",
                "serial_num": serial_num,
                "already_recorded": True,
            }
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
            "message": f"Serial '{serial_num}' recorded as FAIL (test repetition {repetition}): {reason}",
            "unit": unit,
            "decision": "fail",
            "serial_num": f"{serial_num}_{repetition}",
        }

    existing_record = record_packing(serial_num, unit["po_num"], operator_en, shift, remarks)
    if existing_record:
        return {
            "status": "ok",
            "message": _already_packed_message(existing_record),
            "unit": unit,
            "decision": "pass",
            "serial_num": serial_num,
            "already_recorded": True,
        }

    return {
        "status": "ok",
        "message": f"Serial '{serial_num}' packed successfully.",
        "unit": unit,
        "decision": "pass",
        "serial_num": serial_num,
    }