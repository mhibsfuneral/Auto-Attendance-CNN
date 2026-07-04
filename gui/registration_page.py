import os
import threading
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np

from config import AppConfig
from recognition.dataset_manager import DatasetManager
from recognition.facenet_engine import FaceNetEngine
from recognition.embedding_db import EmbeddingDB
from recognition.class_registry import ClassRegistry
from recognition.similarity import compute_consistency_score, quality_label_from_score


class RegistrationPage(ctk.CTkToplevel):
    """Halaman pendaftaran wajah mahasiswa.

    Bisa dipakai dalam 2 mode:
    - Mode tambah baru (default): NIM/Nama/Kelas kosong, bisa diisi bebas.
    - Mode perbarui dataset wajah (existing_student diisi): NIM/Nama/Kelas
      dikunci sesuai data mahasiswa yang dipilih dari Manajer Mahasiswa,
      hanya proses capture ulang foto yang dijalankan. Dataset foto lama
      milik mahasiswa tsb dihapus dan digantikan yang baru.
    """

    def __init__(self, master, initial_kelas=None, existing_student=None, on_complete=None):
        super().__init__(master)

        self.title("Pendaftaran Wajah")
        self.geometry("1500x900")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.dataset_manager = DatasetManager()
        self.db = EmbeddingDB()
        self.class_registry = ClassRegistry()
        self.existing_student = existing_student
        self.on_complete = on_complete

        self.scanning = False
        self.thumbnail_labels = []
        self.captured_faces = []

        self.build_ui()

        if existing_student:
            self.nim_entry.insert(0, existing_student["nim"])
            self.nama_entry.insert(0, existing_student["name"])
            self.kelas_combo.set(existing_student["class"])
            self.nim_entry.configure(state="disabled")
            self.nama_entry.configure(state="disabled")
            self.kelas_combo.configure(state="disabled")
        elif initial_kelas:
            self.kelas_combo.set(initial_kelas)

    def build_ui(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=15, pady=15)

        judul = "PERBARUI DATASET WAJAH" if self.existing_student else "PENDAFTARAN WAJAH MAHASISWA"
        title = ctk.CTkLabel(
            main,
            text=judul,
            font=("Arial", 30, "bold")
        )
        title.pack(pady=20)

        body = ctk.CTkFrame(main)
        body.pack(fill="both", expand=True)

        left = ctk.CTkFrame(body, width=350)
        left.pack(side="left", fill="y", padx=10, pady=10)

        self.nim_entry = self.make_input(left, "NIM")
        self.nama_entry = self.make_input(left, "Nama")

        ctk.CTkLabel(left, text="Kelas", font=("Arial", 16)).pack(pady=(15, 5))
        self.kelas_combo = ctk.CTkComboBox(
            left, width=250, height=40,
            values=self.class_registry.list_classes()
        )
        self.kelas_combo.pack()
        self.kelas_combo.set("")

        self.progress_label = ctk.CTkLabel(
            left,
            text="Progress: 0/30",
            font=("Arial", 18)
        )
        self.progress_label.pack(pady=15)

        self.progress = ctk.CTkProgressBar(left, width=250)
        self.progress.pack(pady=10)
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(
            left,
            text="Status: Belum Scan",
            font=("Arial", 14)
        )
        self.status_label.pack(pady=10)

        ctk.CTkButton(
            left,
            text="Mulai Pemindaian Wajah",
            command=self.start_scan,
            height=45
        ).pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            left,
            text="Selesaikan Pendaftaran",
            command=self.finish_registration,
            height=45
        ).pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            left,
            text="Ulangi Pendaftaran",
            command=self.reset_registration,
            height=45
        ).pack(fill="x", padx=20, pady=10)

        right = ctk.CTkFrame(body)
        right.pack(side="right", fill="both", expand=True)

        self.camera_preview = ctk.CTkLabel(
            right,
            text="LIVE CAMERA PREVIEW",
            width=500,
            height=300
        )
        self.camera_preview.pack(pady=20)

        grid_frame = ctk.CTkFrame(right)
        grid_frame.pack(pady=10)

        for r in range(5):
            for c in range(6):
                box = ctk.CTkFrame(grid_frame, width=70, height=70)
                box.grid(row=r, column=c, padx=5, pady=5)

                label = ctk.CTkLabel(box, text=f"{r*6+c+1}")
                label.place(relx=0.5, rely=0.5, anchor="center")

                self.thumbnail_labels.append(label)

        self.quality_label = ctk.CTkLabel(
            right,
            text="Tingkat akurasi wajah : -",
            font=("Arial", 13)
        )
        self.quality_label.pack(pady=(5, 15))

    def make_input(self, parent, label_text):
        label = ctk.CTkLabel(parent, text=label_text, font=("Arial", 16))
        label.pack(pady=(15, 5))

        entry = ctk.CTkEntry(parent, width=250, height=40)
        entry.pack()
        return entry

    def start_scan(self):
        nim = self.nim_entry.get().strip()
        nama = self.nama_entry.get().strip()
        kelas = self.kelas_combo.get().strip()

        if not nim or not nama or not kelas:
            messagebox.showerror("Error", "Lengkapi semua data")
            return

        # Mode update: bersihkan foto lama di folder mahasiswa ini dulu,
        # supaya tidak tercampur dengan hasil capture baru.
        if self.existing_student:
            old_path = self.dataset_manager.create_student_folder(nim, nama, kelas)
            for fname in list(os.listdir(old_path)):
                try:
                    os.remove(os.path.join(old_path, fname))
                except OSError:
                    pass
        else:
            self.dataset_manager.create_student_folder(nim, nama, kelas)

        if not self.dataset_manager.start_camera():
            messagebox.showerror("Error", "Kamera gagal dibuka")
            return

        self.scanning = True
        self.status_label.configure(text="Status: Scanning...")
        self.update_camera()

    def update_camera(self):
        if not self.scanning:
            return

        frame, ok = self.dataset_manager.get_frame()

        if ok:
            frame, saved, path, face_crop = self.dataset_manager.detect_and_save_face(frame)

            if saved and face_crop is not None:
                count = self.dataset_manager.capture_count
                self.captured_faces.append(face_crop)

                self.progress.set(count / 30)
                self.progress_label.configure(text=f"Progress: {count}/30")

                if count <= len(self.thumbnail_labels):
                    self.thumbnail_labels[count - 1].configure(text="✓")

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((500, 300))

            photo = ImageTk.PhotoImage(img)
            self.camera_preview.configure(image=photo, text="")
            self.camera_preview.image = photo

            if self.dataset_manager.is_complete():
                self.scanning = False
                self.dataset_manager.stop_camera()
                self.status_label.configure(text="Status: Capture selesai")
                messagebox.showinfo("Info", "Capture selesai, klik Selesaikan Pendaftaran")
                return

        self.after(150, self.update_camera)

    def finish_registration(self):
        nim = self.nim_entry.get().strip()
        nama = self.nama_entry.get().strip()
        kelas = self.kelas_combo.get().strip()

        if len(self.captured_faces) == 0:
            messagebox.showerror("Error", "Belum ada data wajah")
            return

        # Generate embeddings untuk 30 wajah pakai FaceNet cukup berat —
        # dijalankan di background thread agar UI tidak freeze.
        self.status_label.configure(text="Status: Membuat embeddings, harap tunggu...")
        faces_snapshot = list(self.captured_faces)  # copy agar thread dapat data stabil
        thread = threading.Thread(
            target=self._generate_and_save,
            args=(nim, nama, kelas, faces_snapshot),
            daemon=True
        )
        thread.start()

    def _generate_and_save(self, nim, nama, kelas, faces):
        """Berjalan di background thread — load FaceNet, generate embedding
        tiap wajah, hitung skor konsistensi (tingkat akurasi wajah), lalu
        simpan rata-ratanya sebagai representasi wajah mahasiswa."""
        try:
            facenet = FaceNetEngine()
            facenet.load_models()

            embeddings = [facenet.get_embedding(face) for face in faces]
            avg_embedding = np.mean(embeddings, axis=0)

            consistency_score = compute_consistency_score(embeddings)
            quality_label = quality_label_from_score(
                consistency_score,
                AppConfig.quality_good_threshold,
                AppConfig.quality_fair_threshold
            )

            # Registrasi baru & perbarui dataset wajah sama-sama langsung
            # tersimpan permanen begitu selesai (tidak melalui staging
            # "Upload ke Program" — konsisten dengan sifat capture kamera
            # yang memang aksi langsung/live).
            self.db.add_student(nim, nama, kelas, avg_embedding, quality_label)
            self.class_registry.add_class(kelas)

            self.after(0, self._on_registration_done, None, quality_label)
        except Exception as e:
            self.after(0, self._on_registration_done, str(e), None)

    def _on_registration_done(self, error, quality_label):
        if error:
            self.status_label.configure(text="Status: Gagal")
            messagebox.showerror("Error", error)
        else:
            self.status_label.configure(text="Status: Registrasi berhasil")
            self.quality_label.configure(text=f"Tingkat akurasi wajah : {quality_label}")
            messagebox.showinfo(
                "Sukses",
                f"Wajah berhasil terdaftar.\nTingkat akurasi wajah: {quality_label}"
            )
            if self.on_complete:
                self.on_complete()

    def reset_registration(self):
        self.scanning = False
        self.dataset_manager.stop_camera()
        self.captured_faces = []

        self.progress.set(0)
        self.progress_label.configure(text="Progress: 0/30")
        self.status_label.configure(text="Status: Belum Scan")
        self.quality_label.configure(text="Tingkat akurasi wajah : -")

        for i, label in enumerate(self.thumbnail_labels):
            label.configure(text=str(i + 1))

        if not self.existing_student:
            self.nim_entry.delete(0, "end")
            self.nama_entry.delete(0, "end")
            self.kelas_combo.set("")

        self.camera_preview.configure(image=None, text="LIVE CAMERA PREVIEW")

    def on_close(self):
        self.scanning = False
        self.dataset_manager.stop_camera()
        self.destroy()
