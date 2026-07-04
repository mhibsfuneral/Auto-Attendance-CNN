import os
import shutil

import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageTk

from config import AppConfig
from recognition.embedding_db import EmbeddingDB
from recognition.class_registry import ClassRegistry
from gui.registration_page import RegistrationPage
from gui.student_edit_dialog import StudentEditDialog

THUMB_SIZE = (90, 90)


def student_folder_path(record):
    """Path folder dataset seorang mahasiswa berdasarkan record saat ini
    (dataset/<kelas>/<nim>_<nama>/)."""
    folder = f"{record['nim']}_{record['name']}".replace(" ", "_")
    return os.path.join(AppConfig.dataset_dir, record["class"], folder)


def first_photo_path(record):
    folder = student_folder_path(record)
    if not os.path.isdir(folder):
        return None
    for fname in sorted(os.listdir(folder)):
        if fname.lower().endswith((".jpg", ".jpeg", ".png")):
            return os.path.join(folder, fname)
    return None


class StudentManagerPage(ctk.CTkToplevel):
    """Halaman "Manajer Mahasiswa" — CRUD mahasiswa terorganisir per kelas.

    Alur staging perubahan:
    - Edit NIM/Nama/Kelas & Hapus mahasiswa -> disimpan sebagai "perubahan
      tertunda" (pending_ops), baru diterapkan ke disk & database saat
      tombol "UPLOAD KE PROGRAM" ditekan.
    - Tambah mahasiswa baru & Perbarui dataset wajah -> langsung tersimpan
      permanen begitu proses capture selesai (aksi kamera bersifat
      langsung/live, tidak melalui staging).
    """

    def __init__(self, master):
        super().__init__(master)

        self.title("Manajer Mahasiswa")
        self.geometry("1500x900")

        self.embedding_db = EmbeddingDB()
        self.class_registry = ClassRegistry()

        self.original_data = self.embedding_db.get_all()
        self.pending_ops = {}   # orig_nim -> {"delete": True} atau {"new_nim":..,"new_name":..,"new_class":..}

        self.selected_nim = None
        self.thumb_cache = {}   # simpan referensi PhotoImage agar tidak di-garbage-collect
        self.tabview = None
        self._tab_names = []   # tracking manual — hindari ketergantungan pada atribut internal CTkTabview

        self.build_ui()

    # ------------------------------------------------------------------ #
    #  Working view (data asli + pending_ops diterapkan, minus pending    #
    #  delete) — dipakai untuk menggambar grid & tab                      #
    # ------------------------------------------------------------------ #

    def working_roster(self):
        roster = {}
        for nim, record in self.original_data.items():
            op = self.pending_ops.get(nim)
            if op and op.get("delete"):
                continue

            rec = dict(record)
            if op:
                rec["nim"] = op.get("new_nim", rec["nim"])
                rec["name"] = op.get("new_name", rec["name"])
                rec["class"] = op.get("new_class", rec["class"])
            rec["_orig_nim"] = nim
            roster[nim] = rec

        return roster

    def roster_by_class(self):
        by_class = {}
        for kelas in self.class_registry.list_classes():
            by_class[kelas] = []

        for rec in self.working_roster().values():
            by_class.setdefault(rec["class"], []).append(rec)

        for kelas in by_class:
            by_class[kelas].sort(key=lambda r: r["name"])

        return by_class

    # ------------------------------------------------------------------ #
    #  UI utama                                                            #
    # ------------------------------------------------------------------ #

    def build_ui(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            main, text="MANAJER MAHASISWA", font=("Arial", 30, "bold")
        ).pack(pady=(10, 20))

        body = ctk.CTkFrame(main)
        body.pack(fill="both", expand=True)

        left = ctk.CTkFrame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        tab_toolbar = ctk.CTkFrame(left, fg_color="transparent")
        tab_toolbar.pack(fill="x")

        ctk.CTkButton(
            tab_toolbar, text="+ Kelas Baru", width=120, height=30,
            command=self.add_class_dialog
        ).pack(side="right", padx=5, pady=5)

        self.tabview = ctk.CTkTabview(left)
        self.tabview.pack(fill="both", expand=True)

        self.rebuild_tabs()

        right = ctk.CTkFrame(body, width=340)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        ctk.CTkLabel(
            right, text="Informasi Mahasiswa", font=("Arial", 18, "bold")
        ).pack(pady=(15, 10))

        self.info_photo_label = ctk.CTkLabel(
            right, text="Belum ada\nmahasiswa dipilih", width=220, height=220,
            fg_color="#e5e7eb"
        )
        self.info_photo_label.pack(pady=10)

        self.info_nim = ctk.CTkLabel(right, text="NIM   : -", font=("Arial", 14), anchor="w")
        self.info_nim.pack(fill="x", padx=20, pady=2)
        self.info_nama = ctk.CTkLabel(right, text="Nama  : -", font=("Arial", 14), anchor="w")
        self.info_nama.pack(fill="x", padx=20, pady=2)
        self.info_kelas = ctk.CTkLabel(right, text="Kelas : -", font=("Arial", 14), anchor="w")
        self.info_kelas.pack(fill="x", padx=20, pady=2)
        self.info_kualitas = ctk.CTkLabel(right, text="Tingkat Akurasi Wajah : -", font=("Arial", 13), anchor="w")
        self.info_kualitas.pack(fill="x", padx=20, pady=(2, 15))

        ctk.CTkButton(
            right, text="Tambahkan Mahasiswa Baru", height=40,
            command=self.open_add_student
        ).pack(fill="x", padx=20, pady=6)

        ctk.CTkButton(
            right, text="Perbarui Dataset Mahasiswa", height=40,
            command=self.open_edit_student
        ).pack(fill="x", padx=20, pady=6)

        ctk.CTkButton(
            right, text="Hapus Data Mahasiswa", height=40,
            fg_color="#c0392b", hover_color="#922b21",
            command=self.delete_selected_student
        ).pack(fill="x", padx=20, pady=6)

        self.pending_label = ctk.CTkLabel(
            right, text="Tidak ada perubahan tertunda", font=("Arial", 12), text_color="gray"
        )
        self.pending_label.pack(pady=(15, 5))

        ctk.CTkButton(
            right, text="UPLOAD KE PROGRAM", height=48,
            font=("Arial", 15, "bold"),
            fg_color="#16a34a", hover_color="#15803d",
            command=self.upload_to_program
        ).pack(fill="x", padx=20, pady=(5, 20))

    # ------------------------------------------------------------------ #
    #  Tab per kelas + grid thumbnail                                      #
    # ------------------------------------------------------------------ #

    def rebuild_tabs(self):
        for tab_name in self._tab_names:
            try:
                self.tabview.delete(tab_name)
            except Exception:
                pass
        self._tab_names = []

        by_class = self.roster_by_class()

        if not by_class:
            self.tabview.add("Belum ada kelas")
            self._tab_names.append("Belum ada kelas")
            return

        for kelas, students in by_class.items():
            tab = self.tabview.add(kelas)
            self._tab_names.append(kelas)
            self.build_class_grid(tab, students)

    def build_class_grid(self, tab, students):
        scroll = ctk.CTkScrollableFrame(tab)
        scroll.pack(fill="both", expand=True)

        if not students:
            ctk.CTkLabel(scroll, text="Belum ada mahasiswa di kelas ini", font=("Arial", 13)).pack(pady=20)
            return

        cols = 6
        for idx, rec in enumerate(students):
            r, c = divmod(idx, cols)

            tile = ctk.CTkFrame(scroll, width=110, height=140)
            tile.grid(row=r, column=c, padx=8, pady=8)
            tile.grid_propagate(False)

            photo_img = self.load_thumbnail(rec)
            img_label = ctk.CTkLabel(tile, image=photo_img, text="" if photo_img else "?", width=90, height=90)
            img_label.pack(pady=(8, 4))

            name_label = ctk.CTkLabel(tile, text=rec["name"], font=("Arial", 12, "bold"))
            name_label.pack()

            pending_tag = ""
            op = self.pending_ops.get(rec["_orig_nim"])
            if op:
                pending_tag = " (tertunda)"
            nim_label = ctk.CTkLabel(tile, text=rec["nim"] + pending_tag, font=("Arial", 10), text_color="gray")
            nim_label.pack()

            for widget in (tile, img_label, name_label, nim_label):
                widget.bind("<Button-1>", lambda e, nim=rec["_orig_nim"]: self.select_student(nim))

    def load_thumbnail(self, rec):
        cache_key = rec["_orig_nim"]
        if cache_key in self.thumb_cache:
            return self.thumb_cache[cache_key]

        path = first_photo_path(rec)
        if not path:
            return None

        try:
            img = Image.open(path).resize(THUMB_SIZE)
            photo = ImageTk.PhotoImage(img)
            self.thumb_cache[cache_key] = photo
            return photo
        except (OSError, ValueError):
            return None

    # ------------------------------------------------------------------ #
    #  Seleksi & panel info                                                #
    # ------------------------------------------------------------------ #

    def select_student(self, orig_nim):
        self.selected_nim = orig_nim
        rec = self.working_roster().get(orig_nim)
        if not rec:
            return

        self.info_nim.configure(text=f"NIM   : {rec['nim']}")
        self.info_nama.configure(text=f"Nama  : {rec['name']}")
        self.info_kelas.configure(text=f"Kelas : {rec['class']}")
        self.info_kualitas.configure(
            text=f"Tingkat Akurasi Wajah : {rec.get('quality_label', '-')}"
        )

        path = first_photo_path(rec)
        if path:
            try:
                img = Image.open(path).resize((220, 220))
                photo = ImageTk.PhotoImage(img)
                self.info_photo_label.configure(image=photo, text="")
                self.info_photo_label.image = photo
            except (OSError, ValueError):
                self.info_photo_label.configure(image=None, text="Foto tidak\nditemukan")
        else:
            self.info_photo_label.configure(image=None, text="Foto tidak\nditemukan")

    # ------------------------------------------------------------------ #
    #  Tambah / Edit / Hapus                                               #
    # ------------------------------------------------------------------ #

    def open_add_student(self):
        current_tab = self._current_tab_name()
        RegistrationPage(
            self,
            initial_kelas=current_tab,
            on_complete=self.refresh_after_disk_change
        )

    def open_edit_student(self):
        if not self.selected_nim:
            messagebox.showinfo("Info", "Pilih mahasiswa terlebih dahulu dari daftar.")
            return

        rec = self.working_roster().get(self.selected_nim)
        if not rec:
            return

        StudentEditDialog(
            self,
            student=rec,
            class_choices=self.class_registry.list_classes(),
            on_save=self.apply_edit,
            on_update_dataset=self.open_update_dataset
        )

    def apply_edit(self, orig_nim, new_nim, new_name, new_class):
        # Validasi NIM baru tidak bentrok dengan mahasiswa lain (kecuali dirinya sendiri)
        roster = self.working_roster()
        for nim, rec in roster.items():
            if nim != orig_nim and rec["nim"] == new_nim:
                messagebox.showerror("Error", f"NIM {new_nim} sudah dipakai mahasiswa lain.")
                return False

        self.pending_ops[orig_nim] = {
            "new_nim": new_nim,
            "new_name": new_name,
            "new_class": new_class
        }
        self.class_registry.add_class(new_class)
        self.refresh_view()
        return True

    def open_update_dataset(self, rec):
        """Dipanggil dari dialog edit -> buka ulang RegistrationPage dalam
        mode capture ulang (langsung commit, bukan staged)."""
        RegistrationPage(
            self,
            existing_student={"nim": rec["nim"], "name": rec["name"], "class": rec["class"]},
            on_complete=self.refresh_after_disk_change
        )

    def delete_selected_student(self):
        if not self.selected_nim:
            messagebox.showinfo("Info", "Pilih mahasiswa terlebih dahulu dari daftar.")
            return

        rec = self.working_roster().get(self.selected_nim)
        if not rec:
            return

        if not messagebox.askyesno(
            "Konfirmasi",
            f'Hapus mahasiswa "{rec["name"]}" ({rec["nim"]})?\n'
            "Perubahan ini baru permanen setelah Upload ke Program."
        ):
            return

        self.pending_ops[self.selected_nim] = {"delete": True}
        self.selected_nim = None
        self.refresh_view()

    # ------------------------------------------------------------------ #
    #  Tambah kelas baru                                                   #
    # ------------------------------------------------------------------ #

    def add_class_dialog(self):
        dialog = ctk.CTkInputDialog(text="Masukkan kode kelas baru:", title="Kelas Baru")
        kode = dialog.get_input()
        if not kode:
            return

        kode = kode.strip()
        if not kode:
            return

        if not self.class_registry.add_class(kode):
            messagebox.showerror("Error", f"Kelas '{kode}' sudah ada.")
            return

        self.refresh_view()

    # ------------------------------------------------------------------ #
    #  Upload ke Program — commit semua perubahan tertunda                #
    # ------------------------------------------------------------------ #

    def upload_to_program(self):
        if not self.pending_ops:
            messagebox.showinfo("Info", "Tidak ada perubahan tertunda untuk diupload.")
            return

        if not messagebox.askyesno(
            "Konfirmasi Upload",
            f"Terapkan {len(self.pending_ops)} perubahan ke program?\n"
            "Tindakan ini akan mengubah file dataset & database secara permanen."
        ):
            return

        errors = []

        for orig_nim, op in list(self.pending_ops.items()):
            original = self.original_data.get(orig_nim)
            if not original:
                continue

            try:
                if op.get("delete"):
                    self._commit_delete(original)
                else:
                    self._commit_edit(orig_nim, original, op)
            except Exception as e:
                errors.append(f"{original.get('name', orig_nim)}: {e}")

        self.pending_ops = {}
        self.thumb_cache = {}
        self.original_data = self.embedding_db.get_all()
        self.selected_nim = None
        self.refresh_view()

        if errors:
            messagebox.showerror(
                "Sebagian gagal",
                "Beberapa perubahan gagal diterapkan:\n" + "\n".join(errors)
            )
        else:
            messagebox.showinfo("Berhasil", "Semua perubahan berhasil diterapkan ke program.")

    def _commit_delete(self, original):
        folder = student_folder_path(original)
        if os.path.isdir(folder):
            shutil.rmtree(folder)
        self.embedding_db.remove_student(original["nim"])

    def _commit_edit(self, orig_nim, original, op):
        old_folder = student_folder_path(original)

        new_nim = op.get("new_nim", original["nim"])
        new_name = op.get("new_name", original["name"])
        new_class = op.get("new_class", original["class"])

        new_record = dict(original)
        new_record["nim"] = new_nim
        new_record["name"] = new_name
        new_record["class"] = new_class
        new_folder = student_folder_path(new_record)

        if old_folder != new_folder and os.path.isdir(old_folder):
            os.makedirs(os.path.dirname(new_folder), exist_ok=True)
            shutil.move(old_folder, new_folder)

        self.embedding_db.update_student(
            orig_nim, new_nim=new_nim, name=new_name, kelas=new_class
        )
        self.class_registry.add_class(new_class)

    # ------------------------------------------------------------------ #
    #  Refresh helpers                                                     #
    # ------------------------------------------------------------------ #

    def _current_tab_name(self):
        try:
            return self.tabview.get()
        except Exception:
            return None

    def refresh_after_disk_change(self):
        """Dipanggil setelah RegistrationPage berhasil commit langsung ke
        disk (tambah mahasiswa baru / perbarui dataset wajah)."""
        self.original_data = self.embedding_db.get_all()
        self.thumb_cache = {}
        self.refresh_view()

    def refresh_view(self):
        pending_count = len(self.pending_ops)
        if pending_count:
            self.pending_label.configure(
                text=f"{pending_count} perubahan tertunda — klik Upload ke Program",
                text_color="#c0392b"
            )
        else:
            self.pending_label.configure(text="Tidak ada perubahan tertunda", text_color="gray")

        self.rebuild_tabs()
