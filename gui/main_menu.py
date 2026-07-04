import customtkinter as ctk


class MainMenu(ctk.CTkFrame):
    """Layar utama aplikasi — 2 pilihan: Mulai Kelas (presensi) atau
    Manajer Mahasiswa (kelola data mahasiswa per kelas)."""

    def __init__(self, master, on_start_class, on_student_manager):
        super().__init__(master)

        self.on_start_class = on_start_class
        self.on_student_manager = on_student_manager

        title = ctk.CTkLabel(
            self,
            text="AUTOMATIC ATTENDANCE SYSTEM\nUNIVERSITAS AMIKOM YOGYAKARTA",
            font=("Arial", 34, "bold")
        )
        title.pack(pady=70)

        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=50)

        kelas_btn = ctk.CTkButton(
            button_frame,
            text="MULAI KELAS",
            width=280,
            height=180,
            font=("Arial", 24, "bold"),
            command=self.on_start_class
        )
        kelas_btn.grid(row=0, column=0, padx=40)

        manajer_btn = ctk.CTkButton(
            button_frame,
            text="MANAJER MAHASISWA",
            width=280,
            height=180,
            font=("Arial", 24, "bold"),
            command=self.on_student_manager
        )
        manajer_btn.grid(row=0, column=1, padx=40)
