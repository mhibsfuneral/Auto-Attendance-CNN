import customtkinter as ctk
from tkinter import messagebox
from config import AppConfig
from recognition.class_registry import ClassRegistry


class SetupPage(ctk.CTkFrame):
    def __init__(self, master, on_continue):
        super().__init__(master)

        self.on_continue = on_continue

        self.build_ui()

    def build_ui(self):
        container = ctk.CTkFrame(self)
        container.pack(expand=True)

        title = ctk.CTkLabel(
            container,
            text="SETUP KELAS",
            font=("Arial", 34, "bold")
        )
        title.pack(pady=30)

        self.class_registry = ClassRegistry()

        self.lecturer_entry = self.make_input(
            container,
            "Nama Dosen"
        )

        ctk.CTkLabel(container, text="Kode Kelas").pack(pady=(10, 5))
        self.class_entry = ctk.CTkComboBox(
            container, width=400, height=40,
            values=self.class_registry.list_classes()
        )
        self.class_entry.pack(pady=(0, 10))
        if self.class_registry.list_classes():
            self.class_entry.set(self.class_registry.list_classes()[0])

        self.room_entry = self.make_input(
            container,
            "Ruang"
        )

        self.duration_entry = self.make_input(
            container,
            "Durasi (menit)"
        )

        btn = ctk.CTkButton(
            container,
            text="LANJUT",
            width=220,
            height=45,
            command=self.submit
        )
        btn.pack(pady=25)

    def make_input(self, parent, label_text):
        label = ctk.CTkLabel(
            parent,
            text=label_text
        )
        label.pack(pady=(10, 5))

        entry = ctk.CTkEntry(
            parent,
            width=400,
            height=40
        )
        entry.pack(pady=(0, 10))

        return entry

    def submit(self):
        lecturer = self.lecturer_entry.get().strip()
        class_code = self.class_entry.get().strip()
        room = self.room_entry.get().strip()
        duration = self.duration_entry.get().strip()

        if not lecturer or not class_code or not room or not duration:
            messagebox.showerror(
                "Error",
                "Semua field wajib diisi"
            )
            return

        try:
            duration = int(duration)
        except ValueError:
            messagebox.showerror(
                "Error",
                "Durasi harus angka"
            )
            return

        AppConfig.lecturer_name = lecturer
        AppConfig.class_code = class_code
        AppConfig.room = room
        AppConfig.duration = duration

        self.on_continue()