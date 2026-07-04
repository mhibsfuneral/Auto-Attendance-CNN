import customtkinter as ctk
from tkinter import messagebox


class StudentEditDialog(ctk.CTkToplevel):
    """Dialog "Perbarui Dataset Mahasiswa" — edit NIM/Nama/Pindah Kelas
    (disimpan sebagai perubahan tertunda), atau buka ulang alur capture
    untuk memperbarui dataset wajah (langsung commit).
    """

    def __init__(self, master, student, class_choices, on_save, on_update_dataset):
        super().__init__(master)

        self.title("Perbarui Dataset Mahasiswa")
        self.geometry("420x420")
        self.transient(master)
        self.grab_set()

        self.orig_nim = student["_orig_nim"]
        self.student = student
        self.on_save = on_save
        self.on_update_dataset = on_update_dataset

        ctk.CTkLabel(
            self, text="Edit Data Mahasiswa", font=("Arial", 18, "bold")
        ).pack(pady=(20, 15))

        ctk.CTkLabel(self, text="NIM").pack(pady=(5, 2))
        self.nim_entry = ctk.CTkEntry(self, width=300, height=38)
        self.nim_entry.insert(0, student["nim"])
        self.nim_entry.pack()

        ctk.CTkLabel(self, text="Nama").pack(pady=(15, 2))
        self.nama_entry = ctk.CTkEntry(self, width=300, height=38)
        self.nama_entry.insert(0, student["name"])
        self.nama_entry.pack()

        ctk.CTkLabel(self, text="Kelas (Pindah Kelas)").pack(pady=(15, 2))
        self.kelas_combo = ctk.CTkComboBox(self, width=300, height=38, values=class_choices)
        self.kelas_combo.set(student["class"])
        self.kelas_combo.pack()

        ctk.CTkButton(
            self, text="Simpan Perubahan (Tertunda)", height=42,
            command=self.save_changes
        ).pack(pady=(25, 8), padx=30, fill="x")

        ctk.CTkButton(
            self, text="Perbarui Dataset Wajah (ambil ulang foto)", height=42,
            fg_color="#2563eb", hover_color="#1d4ed8",
            command=self.trigger_update_dataset
        ).pack(pady=8, padx=30, fill="x")

    def save_changes(self):
        new_nim = self.nim_entry.get().strip()
        new_name = self.nama_entry.get().strip()
        new_class = self.kelas_combo.get().strip()

        if not new_nim or not new_name or not new_class:
            messagebox.showerror("Error", "Semua field wajib diisi")
            return

        ok = self.on_save(self.orig_nim, new_nim, new_name, new_class)
        if ok:
            self.destroy()

    def trigger_update_dataset(self):
        if not messagebox.askyesno(
            "Konfirmasi",
            "Foto lama mahasiswa ini akan dihapus dan digantikan hasil capture baru.\n"
            "Proses ini langsung tersimpan permanen begitu selesai (tidak melalui Upload ke Program).\n\n"
            "Lanjutkan?"
        ):
            return

        self.destroy()
        self.on_update_dataset(self.student)
