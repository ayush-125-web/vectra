"""
ANPR City-Wide Vehicle Tracking - Query Layer
================================================
Every read-only lookup for a single plate: full trajectory, last
known location, blacklist status. Kept separate from anpr_db.py on
purpose - that file only does schema + inserts, this file only reads.

Usage:
    db = ANPRDatabase()
    engine = PlateQueryEngine(db)
    engine.get_last_known_location("TN01AB1234")
    engine.query("TN01AB1234")   # full report
"""


class PlateQueryEngine:

    def __init__(self, database):
        self.db = database

    def exists(self, plate_number: str) -> bool:
        cur = self.db.conn.cursor()
        cur.execute("SELECT 1 FROM vehicles WHERE plate_number = ?", (plate_number,))
        return cur.fetchone() is not None

    def get_trajectory(self, plate_number, start_time=None, end_time=None) -> list:
        """Full chronological list of detections for one plate, camera info joined in."""
        query = """
            SELECT d.timestamp, d.confidence_score,
                   c.camera_id, c.location_name, c.road_name
            FROM detections d
            JOIN cameras c ON d.camera_id = c.camera_id
            WHERE d.plate_number = ?
        """
        params = [plate_number]
        if start_time:
            query += " AND d.timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND d.timestamp <= ?"
            params.append(end_time)
        query += " ORDER BY d.timestamp ASC"

        cur = self.db.conn.cursor()
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]

    def get_last_known_location(self, plate_number: str):
        """
        The 'last time which car has passed which place' lookup -
        answered straight off the vehicles table (no scanning the
        full detections history) since it's kept up to date on
        every insert.
        """
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT v.plate_number, v.last_seen, v.last_camera_id,
                   c.location_name, c.road_name
            FROM vehicles v
            LEFT JOIN cameras c ON v.last_camera_id = c.camera_id
            WHERE v.plate_number = ?
        """, (plate_number,))
        row = cur.fetchone()
        return dict(row) if row else None

    def is_blacklisted(self, plate_number: str):
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT reason, flagged_on FROM blacklist
            WHERE plate_number = ? AND status = 'active'
            ORDER BY flagged_on DESC LIMIT 1
        """, (plate_number,))
        row = cur.fetchone()
        return dict(row) if row else None

    def query(self, plate_number: str, start_time=None, end_time=None) -> dict:
        """Main entry point - full report for a plate."""
        plate_number = plate_number.strip().upper()

        if not self.exists(plate_number):
            return {
                "plate_number": plate_number,
                "found": False,
                "message": "No record found for this plate."
            }

        route = self.get_trajectory(plate_number, start_time, end_time)
        if not route:
            return {
                "plate_number": plate_number,
                "found": False,
                "message": "Plate exists but has no detections in this time range."
            }

        return {
            "plate_number": plate_number,
            "found": True,
            "total_detections": len(route),
            "total_cameras_crossed": len({r["camera_id"] for r in route}),
            "first_seen": route[0],
            "last_known_location": self.get_last_known_location(plate_number),
            "route": route,
            "blacklist_status": self.is_blacklisted(plate_number)
        }

    def print_report(self, plate_number: str, start_time=None, end_time=None) -> dict:
        """Pretty-prints the report to console - handy for demos."""
        report = self.query(plate_number, start_time, end_time)

        print(f"\n{'=' * 50}")
        print(f"TRAJECTORY REPORT: {report['plate_number']}")
        print(f"{'=' * 50}")

        if not report["found"]:
            print(report["message"])
            return report

        last = report["last_known_location"]
        print(f"Total cameras crossed : {report['total_cameras_crossed']}")
        print(f"Total detections      : {report['total_detections']}")
        if last:
            print(f"Last known location   : {last['location_name']} "
                  f"({last['last_camera_id']}) at {last['last_seen']}")

        if report["blacklist_status"]:
            print(f"\u26a0 BLACKLISTED         : {report['blacklist_status']['reason']} "
                  f"(flagged {report['blacklist_status']['flagged_on']})")

        print("\nFull route:")
        for i, stop in enumerate(report["route"], 1):
            print(f"  {i}. {stop['timestamp']} | {stop['location_name']} "
                  f"({stop['camera_id']}) | confidence={stop['confidence_score']}")

        return report