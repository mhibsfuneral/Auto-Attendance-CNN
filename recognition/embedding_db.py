import os
import pickle

from config import AppConfig


class EmbeddingDB:
    """Menyimpan data mahasiswa terdaftar beserta embedding wajah (vektor
    512 dimensi dari FaceNet, dirata-rata dari beberapa sample capture)
    yang dipakai untuk pengenalan via cosine similarity.

    Setiap record: {nim, name, class, embedding, quality_label}
    """

    def __init__(self):
        self.db_path = AppConfig.embeddings_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def load(self):
        if not os.path.exists(self.db_path):
            return {}

        with open(self.db_path, "rb") as f:
            return pickle.load(f)

    def save(self, data):
        with open(self.db_path, "wb") as f:
            pickle.dump(data, f)

    def add_student(self, nim, name, kelas, embedding, quality_label="-"):
        data = self.load()

        data[nim] = {
            "nim": nim,
            "name": name,
            "class": kelas,
            "embedding": embedding,
            "quality_label": quality_label
        }

        self.save(data)

    def update_student(self, old_nim, new_nim=None, name=None, kelas=None):
        """Perbarui metadata mahasiswa (dipanggil saat commit "Upload ke
        Program" untuk perubahan NIM/Nama/Kelas). Embedding tidak diubah
        oleh operasi ini — hanya berubah lewat re-capture dataset wajah.

        Jika NIM berubah, key dictionary ikut di-re-key.
        """
        data = self.load()

        if old_nim not in data:
            return False

        record = data.pop(old_nim)

        final_nim = new_nim or old_nim
        record["nim"] = final_nim
        if name is not None:
            record["name"] = name
        if kelas is not None:
            record["class"] = kelas

        data[final_nim] = record
        self.save(data)
        return True

    def remove_student(self, nim):
        data = self.load()

        if nim in data:
            del data[nim]
            self.save(data)

    def get_all(self):
        return self.load()

    def get_by_class(self, kelas):
        return {
            nim: rec for nim, rec in self.load().items()
            if rec.get("class") == kelas
        }
