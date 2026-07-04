import json
import os

from config import AppConfig


class ClassRegistry:
    """Mengelola daftar kode kelas (TK01, TK02, TK03, dst.) yang dipakai
    di seluruh aplikasi — Setup Kelas (dropdown), Manajer Mahasiswa (tab
    per kelas), dan validasi saat pendaftaran/pemindahan mahasiswa.

    Daftar kelas disimpan terpisah dari folder dataset/ (models/classes.json)
    supaya kelas yang baru dibuat lewat tombol "+" tapi belum punya mahasiswa
    tetap muncul sebagai tab kosong.
    """

    def __init__(self):
        self.path = AppConfig.classes_path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _load_raw(self):
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _save_raw(self, classes):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(classes, f, indent=2, ensure_ascii=False)

    def list_classes(self):
        """Kembalikan daftar kelas gabungan dari classes.json DAN folder
        dataset/ yang sudah ada (jaga-jaga jika ada folder dataset lama
        yang belum tercatat di classes.json)."""
        classes = set(self._load_raw())

        if os.path.isdir(AppConfig.dataset_dir):
            for entry in os.listdir(AppConfig.dataset_dir):
                full_path = os.path.join(AppConfig.dataset_dir, entry)
                if os.path.isdir(full_path):
                    classes.add(entry)

        return sorted(classes)

    def add_class(self, kode_kelas):
        kode_kelas = kode_kelas.strip()
        if not kode_kelas:
            return False

        classes = set(self._load_raw())
        if kode_kelas in classes:
            return False

        classes.add(kode_kelas)
        self._save_raw(sorted(classes))

        os.makedirs(os.path.join(AppConfig.dataset_dir, kode_kelas), exist_ok=True)
        return True

    def remove_class(self, kode_kelas):
        """Hapus kelas dari registry (dipanggil hanya jika kelas tidak lagi
        punya mahasiswa terdaftar — pengecekan itu tanggung jawab caller)."""
        classes = set(self._load_raw())
        classes.discard(kode_kelas)
        self._save_raw(sorted(classes))
