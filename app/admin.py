from app.db import query_all, query_one

def get_packing_logs(limit: int = 200):
    return query_all(
        """
        SELECT serial_num, po_num, operator_en, shift, date_time, test_rep, remarks, status
        FROM energous.esense_fvi
        ORDER BY date_time DESC
        LIMIT %s
        """,
        (limit,)
    )

def get_operator_summary():
    return query_all(
        """
        SELECT
            operator_en,
            COUNT(*)            AS total_scanned,
            SUM(status = 1)     AS total_pass,
            MAX(date_time)      AS last_scan
        FROM energous.esense_fvi
        GROUP BY operator_en
        ORDER BY total_scanned DESC
        """
    )

def get_daily_summary():
    return query_all(
        """
        SELECT
            DATE(date_time)     AS scan_date,
            COUNT(*)            AS total,
            SUM(status = 1)     AS passed
        FROM energous.esense_fvi
        GROUP BY scan_date
        ORDER BY scan_date DESC
        LIMIT 30
        """
    )

def get_recent_by_operator(operator_en: str, limit: int = 50):
    return query_all(
        """
        SELECT serial_num, po_num, shift, date_time, status, remarks
        FROM energous.esense_fvi
        WHERE operator_en = %s
        ORDER BY date_time DESC
        LIMIT %s
        """,
        (operator_en, limit)
    )
