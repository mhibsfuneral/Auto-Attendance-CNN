import csv
import os
from datetime import datetime
from config import AppConfig


class AttendanceManager:
    def __init__(self):
        self.attendance_file = AppConfig.attendance_csv
        self.present_students = set()

        self.ensure_csv()

    def ensure_csv(self):
        if not os.path.exists(self.attendance_file):
            with open(self.attendance_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "No",
                    "NIM",
                    "Nama",
                    "Waktu",
                    "Status"
                ])

    def mark_attendance(self, nim, name, status="Hadir"):
        if nim in self.present_students:
            return None

        rows = self.read_all()
        no = len(rows) + 1

        timestamp = datetime.now().strftime("%H:%M:%S")

        row = [no, nim, name, timestamp, status]

        with open(self.attendance_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)

        self.present_students.add(nim)
        return row

    def read_all(self):
        rows = []

        if not os.path.exists(self.attendance_file):
            return rows

        with open(self.attendance_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)

            for row in reader:
                rows.append(row)

        return rows

    def remove_attendance(self, nim):
        rows = self.read_all()
        new_rows = []

        removed = False

        for row in rows:
            if row[1] != nim:
                new_rows.append(row)
            else:
                removed = True

        with open(self.attendance_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow([
                "No",
                "NIM",
                "Nama",
                "Waktu",
                "Status"
            ])

            for i, row in enumerate(new_rows, start=1):
                row[0] = i
                writer.writerow(row)

        if nim in self.present_students:
            self.present_students.remove(nim)

        return removed