import customtkinter as ctk
from gui.setup_page import SetupPage
from gui.main_menu import MainMenu
from gui.attendance_page import AttendancePage
from gui.student_manager_page import StudentManagerPage

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class FaceRecognitionApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Automatic Attendance System")
        self.geometry("1400x850")
        self.minsize(1200, 700)

        self.current_page = None

        self.after(100, self.show_main_menu)

    def clear_page(self):
        if self.current_page:
            self.current_page.destroy()
            self.current_page = None

    def show_main_menu(self):
        try:
            self.clear_page()

            self.current_page = MainMenu(
                master=self,
                on_start_class=self.show_setup_page,
                on_student_manager=self.open_student_manager
            )

            self.current_page.pack(
                fill="both",
                expand=True
            )

        except Exception as e:
            print("MAIN MENU ERROR:", e)

    def show_setup_page(self):
        try:
            self.clear_page()

            self.current_page = SetupPage(
                master=self,
                on_continue=self.open_attendance_page
            )

            self.current_page.pack(
                fill="both",
                expand=True
            )

        except Exception as e:
            print("SETUP PAGE ERROR:", e)

    def open_attendance_page(self):
        """Dipanggil setelah Setup Kelas selesai. Kembalikan layar dasar ke
        Main Menu, lalu buka jendela presensi (AttendancePage) di atasnya."""
        try:
            self.show_main_menu()
            AttendancePage(self)
        except Exception as e:
            print("ATTENDANCE PAGE ERROR:", e)

    def open_student_manager(self):
        try:
            StudentManagerPage(self)
        except Exception as e:
            print("STUDENT MANAGER ERROR:", e)


if __name__ == "__main__":
    app = FaceRecognitionApp()
    app.mainloop()
