import threading
import csv
from datetime import datetime, timedelta

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import cv2

from config import AppConfig
from recognition.facenet_engine import FaceNetEngine
from recognition.attendance_manager import AttendanceManager
from recognition.embedding_db import EmbeddingDB

# Nama bulan dalam Bahasa Indonesia (tidak bergantung pada locale OS)
BULAN_INDONESIA = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}


def format_tanggal_indonesia(dt):
    return f"{dt.day} {BULAN_INDONESIA[dt.month]} {dt.year}"


def format_durasi(total_menit):
    jam = total_menit // 60
    menit = total_menit % 60
    return f"{jam:02d}:{menit:02d}:00"


class AttendancePage(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)

        self.title("Attendance Monitoring")
        self.geometry("1600x950")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.engine = None
        self.attendance_manager = AttendanceManager()
        self.running = False
        self._loading = False
        self.camera_label = None  # hanya ada saat panel "Scanning Wajah" aktif

        # Mencatat NIM yang sudah hadir — tiap mahasiswa hanya tampil 1x
        self.present_nims = set()

        # Mencatat NIM mahasiswa dari kelas LAIN yang terdeteksi kamera —
        # tetap ditampilkan/dicatat (dengan penanda), tapi tidak dihitung
        # sebagai kehadiran resmi kelas ini.
        self.foreign_nims = set()

        # True setelah waktu presensi habis — menghentikan scanning &
        # mengunci panel menu ke tampilan "Waktu Habis".
        self.time_up = False

        # Debounce: catat NIM terakhir yang terdeteksi agar mark_student()
        # tidak dipanggil 30x/detik untuk hasil cache yang sama
        self._last_detected_nim = None

        # Info sesi untuk panel Status
        self.login_time = datetime.now()
        self.session_end = self.login_time + timedelta(minutes=AppConfig.duration)

        self.build_ui()
        self.update_timer()

    # ------------------------------------------------------------------ #
    #  Layout utama                                                        #
    # ------------------------------------------------------------------ #

    def build_ui(self):
        self.build_header()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Kolom kiri: Menu/Scanning (atas) + Status (bawah) — lebar tetap
        self.left_col = ctk.CTkFrame(body, width=360)
        self.left_col.pack(side="left", fill="y", padx=(0, 10))
        self.left_col.pack_propagate(False)

        # Kolom kanan: Daftar Presensi Mahasiswa
        right_col = ctk.CTkFrame(body)
        right_col.pack(side="left", fill="both", expand=True)

        # Container panel atas (akan diisi build_menu_panel / build_scanning_panel)
        self.panel_frame = ctk.CTkFrame(self.left_col)
        self.panel_frame.pack(fill="x", pady=(0, 10))

        # Panel Status (selalu tampil, tidak berubah)
        self.status_frame = ctk.CTkFrame(self.left_col)
        self.status_frame.pack(fill="both", expand=True)

        self.build_menu_panel()
        self.build_status_panel()
        self.build_table(right_col)

    def build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="INTERNET OF THINGS",
            font=("Arial", 32, "bold")
        ).pack()

        # Field yang diisi dosen saat Setup Kelas
        ctk.CTkLabel(
            header,
            text=AppConfig.lecturer_name,
            font=("Arial", 14)
        ).pack()

        ctk.CTkLabel(
            header,
            text="Program Sarjana - Ilmu Komputer - Teknik Komputer",
            font=("Arial", 14)
        ).pack()

        ctk.CTkLabel(
            header,
            text=AppConfig.class_code,
            font=("Arial", 14)
        ).pack()

    # ------------------------------------------------------------------ #
    #  Panel Menu (state awal)                                            #
    # ------------------------------------------------------------------ #

    def clear_panel(self):
        for widget in self.panel_frame.winfo_children():
            widget.destroy()

    def build_menu_panel(self):
        self.clear_panel()
        self.camera_label = None

        ctk.CTkLabel(
            self.panel_frame,
            text="Menu",
            font=("Arial", 16, "bold"),
            anchor="w"
        ).pack(fill="x", padx=15, pady=(15, 10))

        menu_items = [
            ("Mulai Scanning Wajah", self.switch_to_scanning, True),
            ("Presensi Manual", lambda: self.placeholder("Presensi Manual"), False),
            ("Gagalkan Presensi", lambda: self.placeholder("Gagalkan Presensi"), False),
            ("Edit Resume Materi", lambda: self.placeholder("Edit Resume Materi"), False),
            ("Presensi Asisten", lambda: self.placeholder("Presensi Asisten"), False),
            ("Kelas Selesai", self.selesai_kelas, True),
        ]

        for label_text, command, enabled in menu_items:
            btn = ctk.CTkButton(
                self.panel_frame,
                text=label_text,
                command=command,
                anchor="w",
                height=40,
                fg_color="#2563eb" if enabled else "#9ca3af",
                hover_color="#1d4ed8" if enabled else "#9ca3af",
                state="normal" if enabled else "disabled"
            )
            btn.pack(fill="x", padx=15, pady=5)

    def build_timeup_panel(self):
        """Panel pengganti saat waktu presensi habis — kamera sudah
        dihentikan otomatis, dosen harus menekan tombol ini secara manual
        untuk menyimpan riwayat presensi & menutup sesi."""
        self.clear_panel()
        self.camera_label = None

        ctk.CTkLabel(
            self.panel_frame,
            text="⏰ Waktu Presensi Habis",
            font=("Arial", 18, "bold"),
            text_color="#c0392b"
        ).pack(padx=15, pady=(30, 10))

        ctk.CTkLabel(
            self.panel_frame,
            text="Kamera sudah dihentikan otomatis.\n"
                 "Klik tombol di bawah untuk menyimpan\n"
                 "riwayat presensi dan menutup sesi ini.",
            font=("Arial", 13),
            justify="center"
        ).pack(padx=15, pady=(0, 20))

        ctk.CTkButton(
            self.panel_frame,
            text="Simpan & Tutup",
            command=self.selesai_kelas,
            height=45,
            fg_color="#c0392b",
            hover_color="#922b21"
        ).pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(self.panel_frame, text="", height=5).pack()

    # ------------------------------------------------------------------ #
    #  Panel Scanning Wajah (state setelah Mulai Scanning Wajah ditekan)  #
    # ------------------------------------------------------------------ #

    def build_scanning_panel(self):
        self.clear_panel()

        ctk.CTkLabel(
            self.panel_frame,
            text="Scanning Wajah",
            font=("Arial", 16, "bold"),
            anchor="w"
        ).pack(fill="x", padx=15, pady=(15, 10))

        self.camera_label = ctk.CTkLabel(
            self.panel_frame,
            text="Memuat kamera...",
            width=320,
            height=320,
            fg_color="#e5e7eb"
        )
        self.camera_label.pack(padx=15, pady=(0, 10))

        ctk.CTkButton(
            self.panel_frame,
            text="Presensi Manual",
            command=lambda: self.placeholder("Presensi Manual"),
            anchor="w",
            height=40,
            fg_color="#9ca3af",
            hover_color="#9ca3af",
            state="disabled"
        ).pack(fill="x", padx=15, pady=5)

        # Tombol "Selesaikan Kelas" — bisa diakses langsung dari panel
        # Scanning Wajah, otomatis ekspor CSV riwayat presensi seperti biasa.
        ctk.CTkButton(
            self.panel_frame,
            text="Selesaikan Kelas",
            command=self.selesai_kelas,
            anchor="w",
            height=40,
            fg_color="#c0392b",
            hover_color="#922b21"
        ).pack(fill="x", padx=15, pady=(5, 15))

    def switch_to_scanning(self):
        if self.time_up:
            return
        self.build_scanning_panel()
        self.start_camera()

    def switch_to_menu(self):
        self.stop_camera()
        self.build_menu_panel()

    def placeholder(self, nama_fitur):
        messagebox.showinfo(
            "Segera Hadir",
            f'Fitur "{nama_fitur}" belum diimplementasikan.'
        )

    # ------------------------------------------------------------------ #
    #  Panel Status                                                        #
    # ------------------------------------------------------------------ #

    def build_status_panel(self):
        ctk.CTkLabel(
            self.status_frame,
            text="Status",
            font=("Arial", 16, "bold"),
            anchor="w"
        ).pack(fill="x", padx=15, pady=(15, 10))

        jumlah_mhs = len(EmbeddingDB().get_by_class(AppConfig.class_code))

        rows = [
            ("Ruang", AppConfig.room or "online"),
            ("Tanggal", format_tanggal_indonesia(datetime.now())),
            ("Lama Sesi", format_durasi(AppConfig.duration)),
            ("Waktu Login", self.login_time.strftime("%H:%M:%S")),
            ("Waktu Selesai", self.session_end.strftime("%H:%M:%S")),
            ("Sisa Waktu", "--:--:--"),
            ("Jumlah Mhs", str(jumlah_mhs)),
        ]

        self.status_value_labels = {}

        for label_text, value_text in rows:
            row = ctk.CTkFrame(self.status_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)

            ctk.CTkLabel(
                row, text=label_text, width=110, anchor="w", font=("Arial", 13)
            ).pack(side="left")

            value_label = ctk.CTkLabel(
                row, text=value_text, anchor="w", font=("Arial", 13, "bold")
            )
            value_label.pack(side="left")

            self.status_value_labels[label_text] = value_label

    def update_timer(self):
        remaining = self.session_end - datetime.now()
        total_seconds = int(remaining.total_seconds())

        if total_seconds <= 0:
            self.status_value_labels["Sisa Waktu"].configure(text="Waktu Habis")
            if not self.time_up:
                self.time_up = True
                self._on_time_up()
            return  # berhenti menjadwalkan ulang, waktu sudah habis

        jam = total_seconds // 3600
        menit = (total_seconds % 3600) // 60
        detik = total_seconds % 60
        text = f"{jam:02d}:{menit:02d}:{detik:02d}"

        self.status_value_labels["Sisa Waktu"].configure(text=text)
        self.after(1000, self.update_timer)

    def _on_time_up(self):
        """Waktu presensi habis — hentikan kamera & kunci panel ke tampilan
        "Waktu Habis". Sesuai keputusan desain: TIDAK auto-save, dosen yang
        menekan tombol "Simpan & Tutup" secara manual."""
        self.running = False
        self.stop_camera()
        self.build_timeup_panel()

    # ------------------------------------------------------------------ #
    #  Tabel Daftar Presensi Mahasiswa                                     #
    # ------------------------------------------------------------------ #

    def build_table(self, parent):
        ctk.CTkLabel(
            parent,
            text="Daftar Presensi Mahasiswa",
            font=("Arial", 16, "bold"),
            anchor="w"
        ).pack(fill="x", padx=15, pady=(15, 10))

        columns = ("No", "NIM", "Nama", "Jam Presensi", "Kelas")
        self.tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            height=30
        )

        widths = {"No": 50, "NIM": 140, "Nama": 200, "Jam Presensi": 120, "Kelas": 140}

        for col in columns:
            self.tree.heading(col, text=col.upper() if col != "Jam Presensi" else "JAM PRESENSI")
            self.tree.column(col, width=widths[col], anchor="center")

        self.tree.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Baris mahasiswa dari kelas LAIN ditandai hijau — visual cue bagi
        # dosen bahwa mahasiswa tsb seharusnya tidak berada di kelas ini.
        self.tree.tag_configure("foreign", foreground="#16a34a")

    # ------------------------------------------------------------------ #
    #  Kamera & model loading                                              #
    # ------------------------------------------------------------------ #

    def start_camera(self):
        if self.running or self._loading:
            return

        if self.engine is None:
            try:
                self.engine = FaceNetEngine()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

        self._loading = True
        if self.camera_label is not None:
            self.camera_label.configure(text="Loading models, harap tunggu...")

        thread = threading.Thread(target=self._load_and_start, daemon=True)
        thread.start()

    def _load_and_start(self):
        try:
            success = self.engine.start_camera()
        except Exception as e:
            self.after(0, self._on_load_error, str(e))
            return
        self.after(0, self._on_camera_started, success)

    def _on_load_error(self, message):
        self._loading = False
        messagebox.showerror("Error", message)
        if self.camera_label is not None:
            self.camera_label.configure(text="Gagal memuat kamera")

    def _on_camera_started(self, success):
        self._loading = False
        if not success:
            messagebox.showerror("Error", "Kamera gagal dibuka")
            if self.camera_label is not None:
                self.camera_label.configure(text="Kamera gagal dibuka")
            return
        self.running = True
        self.update_camera()

    def stop_camera(self):
        self.running = False
        if self.engine is not None:
            self.engine.stop_camera()

    # ------------------------------------------------------------------ #
    #  Tandai kehadiran                                                    #
    # ------------------------------------------------------------------ #

    def mark_student(self, student):
        nim = student["nim"]
        name = student["name"]
        student_class = student.get("class", "-")

        is_foreign = student_class != AppConfig.class_code

        # Setiap mahasiswa hanya tampil 1x — yang pertama tampil = baris teratas
        if is_foreign:
            if nim in self.foreign_nims:
                return
            self.foreign_nims.add(nim)
        else:
            if nim in self.present_nims:
                return
            self.present_nims.add(nim)

        now = datetime.now().strftime("%H:%M:%S")
        no = len(self.tree.get_children()) + 1

        if is_foreign:
            # Keterangan langsung di kolom Nama & Kelas supaya ikut terbawa
            # saat diekspor ke CSV (poin 2: presensi tetap dicatat, tapi
            # ditandai berasal dari kelas lain).
            display_name = f"{name} (Kelas Lain)"
            display_class = f"{student_class} ≠ {AppConfig.class_code}"
            row = (no, nim, display_name, now, display_class)
            self.tree.insert("", "end", values=row, tags=("foreign",))
            status = f"Hadir (Kelas Lain: {student_class})"
        else:
            row = (no, nim, name, now, student_class)
            self.tree.insert("", "end", values=row)
            status = "Hadir"

        try:
            self.attendance_manager.mark_attendance(nim, name, status)
        except Exception as e:
            print("Attendance CSV error:", e)

    # ------------------------------------------------------------------ #
    #  Loop kamera (optimized — non-blocking dengan inference thread)      #
    # ------------------------------------------------------------------ #

    def update_camera(self):
        if not self.running:
            return

        try:
            # get_frame() sekarang non-blocking — langsung kembalikan cache
            frame, student, confidence = self.engine.get_frame()
        except Exception as e:
            if self.camera_label is not None:
                self.camera_label.configure(text=f"Engine Error: {str(e)}")
            self.after(200, self.update_camera)
            return

        if frame is not None:
            # Hanya panggil mark_student() saat ada perubahan deteksi
            # (bukan setiap tick 30fps dengan data cache yang sama).
            # Ini mencegah penulisan CSV berulang dan log duplikat.
            current_nim = student["nim"] if student else None
            if current_nim != self._last_detected_nim:
                self._last_detected_nim = current_nim
                if student:
                    self.mark_student(student)

            if self.camera_label is not None:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Resize dengan INTER_NEAREST — paling cepat untuk preview
                img = Image.fromarray(
                    cv2.resize(frame_rgb, (320, 320),
                               interpolation=cv2.INTER_NEAREST)
                )

                photo = ImageTk.PhotoImage(img)
                self.camera_label.configure(image=photo, text="")
                self.camera_label.image = photo

        # 30ms = ~33 FPS — aman karena get_frame() sudah non-blocking
        self.after(30, self.update_camera)

    # ------------------------------------------------------------------ #
    #  Kelas Selesai — ekspor CSV sesi                                     #
    # ------------------------------------------------------------------ #

    def selesai_kelas(self):
        self.stop_camera()

        jumlah = len(self.tree.get_children())
        if jumlah == 0:
            if not messagebox.askyesno(
                "Konfirmasi",
                "Belum ada mahasiswa yang hadir.\nTetap selesaikan kelas?"
            ):
                return

        tanggal = datetime.now().strftime("%Y-%m-%d")
        kode = AppConfig.class_code or "kelas"
        default_name = f"presensi_{kode}_{tanggal}.csv"

        filepath = filedialog.asksaveasfilename(
            title="Simpan Rekap Presensi",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_name
        )

        if not filepath:
            messagebox.showinfo("Info", "Sesi kelas telah berakhir.\nFile presensi tidak disimpan.")
            self.destroy()
            return

        self._export_csv(filepath)

    def _export_csv(self, filepath):
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                writer.writerow(["REKAP PRESENSI MAHASISWA"])
                writer.writerow(["Dosen", AppConfig.lecturer_name])
                writer.writerow(["Kode Kelas", AppConfig.class_code])
                writer.writerow(["Ruang", AppConfig.room])
                writer.writerow(["Tanggal", format_tanggal_indonesia(datetime.now())])
                writer.writerow(["Durasi", f"{AppConfig.duration} menit"])
                writer.writerow(["Total Hadir", len(self.present_nims)])
                writer.writerow(["Total Terdeteksi Kelas Lain", len(self.foreign_nims)])
                writer.writerow([])

                writer.writerow(["No", "NIM", "Nama", "Jam Presensi", "Kelas"])

                for item in self.tree.get_children():
                    writer.writerow(self.tree.item(item)["values"])

            messagebox.showinfo("Berhasil", f"Rekap presensi berhasil disimpan:\n{filepath}")
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan file:\n{str(e)}")

    # ------------------------------------------------------------------ #
    #  Tutup jendela                                                       #
    # ------------------------------------------------------------------ #

    def on_close(self):
        if self.running or len(self.present_nims) > 0 or len(self.foreign_nims) > 0:
            if not messagebox.askyesno(
                "Konfirmasi",
                "Sesi belum diselesaikan. Tutup tanpa menyimpan rekap?"
            ):
                return
        self.running = False
        if self.engine is not None:
            self.engine.stop_camera()
        self.destroy()
