from datetime import datetime
from app.db import query_one, get_conn

REQUIRED_STATIONS = ("progtest", "assembly", "lasermarking1", "vi", "ft1", "ft2", "lasermarking2",)

def lookup_unit(serial_num: str):
    """Check b2btag_main for the serial and its station statuses."""
    return query_one(
        """
        SELECT serial_num, po_num, progtest, assembly, lasermarking1, vi,ft1,ft2,lasermarking2
        FROM energous.esense_main_copy
        WHERE serial_num = %s
        LIMIT 1
        """,
        (serial_num,)
    )

def already_packed(serial_num: str) -> bool:
    row = query_one(
        "SELECT serial_num FROM energous.esense_fvi_copy WHERE serial_num = %s LIMIT 1",
        (serial_num,)
    )
    return row is not None

def stations_passed(row: dict) -> bool:
    """Return True if all required stations are recorded as 1."""
    return all(row.get(s) == 1 for s in REQUIRED_STATIONS)

def record_packing(serial_num: str, po_num: str, operator_en: str, shift: str, remarks: str = ""):
    """
    Atomically:
      1. Set fvi=1 in b2btag_main
      2. Insert a row into b2btag_fvi (status=1, test_rep=1)
    """
    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE energous.esense_main_copy
            SET fvi = 1
            WHERE serial_num = %s
            """,
            (serial_num,)
        )

        cur.execute(
            """
            INSERT INTO energous.esense_fvi_copy
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


def process_scan(serial_num: str, operator_en: str, shift: str, remarks: str = ""):
    """
    Full scan pipeline. Returns a result dict:
      status  : "ok" | "already_packed" | "fail" | "not_found"
      message : human-readable string
      unit    : the b2btag_main row (or None)
    """
    serial_num = serial_num.strip()

    unit = lookup_unit(serial_num)
    if not unit:
        return {"status": "not_found", "message": f"Serial '{serial_num}' not found in database.", "unit": None}

    if already_packed(serial_num):
        return {"status": "already_packed", "message": f"Serial '{serial_num}' was already scanned.", "unit": unit}

    if not stations_passed(unit):
        failed = [s for s in REQUIRED_STATIONS if unit.get(s) != 1]
        return {
            "status": "fail",
            "message": f"Serial '{serial_num}' has not passed: {', '.join(failed).upper()}.",
            "unit": unit,
        }

    record_packing(serial_num, unit["po_num"], operator_en, shift, remarks)
    return {
        "status": "ok",
        "message": f"Serial '{serial_num}' packed successfully.",
        "unit": unit,
    }
