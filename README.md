# Automatic Attendance System — Versi CNN (FaceNet + MTCNN)

Sistem presensi otomatis berbasis face recognition dengan **manajemen
multi-kelas**: mahasiswa dikelompokkan per kelas (TK01, TK02, TK03, dst.),
dengan modul **Manajer Mahasiswa** untuk CRUD data mahasiswa lintas kelas.

## Alur aplikasi (sesuai blueprint)

1. **Main Menu** — tampil pertama saat aplikasi dibuka. 2 pilihan:
   **Mulai Kelas** dan **Manajer Mahasiswa**.
2. **Mulai Kelas** → **Setup Kelas** (Nama Dosen, Kode Kelas — dropdown
   dari kelas yang terdaftar, Ruang, Durasi) → **Halaman Presensi**
   (Menu Scanning, Daftar Presensi, Status sesi dengan timer).
3. **Manajer Mahasiswa** → halaman dengan tab per kelas, grid foto
   mahasiswa, panel info, dan tombol Tambah/Edit/Hapus/Upload.
4. **Tambahkan Mahasiswa Baru** (dari Manajer Mahasiswa) → halaman
   Pendaftaran Wajah Mahasiswa (capture 30 foto → generate embedding).

## Fitur baru pada update ini

### 1. Manajemen multi-kelas
- Kelas dikelola lewat `recognition/class_registry.py` — daftar kelas
  disimpan di `models/classes.json`, otomatis sinkron dengan folder
  `dataset/<kelas>/` yang ada.
- Struktur dataset diubah dari flat (`dataset/<nim>_<nama>_<kelas>/`)
  menjadi **per-kelas** (`dataset/<kelas>/<nim>_<nama>/`) — dataset 6
  mahasiswa yang sudah ada otomatis dimigrasikan ke struktur baru ini.
- **Setup Kelas**: field "Kode Kelas" kini dropdown berisi kelas yang
  sudah terdaftar (tetap bisa diketik manual jika perlu).

### 2. Deteksi mahasiswa dari kelas lain (highlight hijau)
Sistem tetap mengenali wajah terlepas dari kelas mana pun mahasiswa itu
terdaftar (matching dilakukan terhadap **seluruh** database, bukan
difilter per kelas) — supaya identitas mahasiswa dari kelas lain tetap
bisa dikenali namanya. Saat AppConfig.class_code (kelas yang sedang
berlangsung) **tidak sama** dengan kelas asal mahasiswa yang terdeteksi:
- Baris pada tabel presensi ditampilkan **hijau**, dengan keterangan
  "(Kelas Lain)" pada nama dan kelas aslinya pada kolom Kelas.
- Tetap tercatat ke `attendance.csv` dengan status
  `"Hadir (Kelas Lain: <kode kelas asli>)"` — sehingga tetap terlacak
  saat presensi diekspor, tapi tidak dihitung ke "Jumlah Hadir" resmi
  kelas yang sedang berlangsung.
- Panel status "Jumlah Mhs" difilter sesuai kelas sesi yang aktif
  (`EmbeddingDB.get_by_class()`), bukan total seluruh mahasiswa semua kelas.

### 3. Manajer Mahasiswa (`gui/student_manager_page.py`)
Halaman baru untuk CRUD data mahasiswa:
- **Tab per kelas** (+ tombol "+ Kelas Baru" untuk menambah kelas kosong)
- **Grid thumbnail** foto mahasiswa per kelas (foto pertama dari dataset
  masing-masing), klik untuk memilih & menampilkan info detail
  (NIM, Nama, Kelas, foto besar, **Tingkat Akurasi Wajah**)
- **Tambahkan Mahasiswa Baru** — membuka halaman pendaftaran wajah,
  otomatis default ke kelas tab yang sedang aktif
- **Perbarui Dataset Mahasiswa** — dialog edit NIM/Nama/Pindah Kelas,
  atau ambil ulang foto wajah (re-capture)
- **Hapus Data Mahasiswa** — hapus mahasiswa terpilih (dataset foto +
  entry database)

**Model staging perubahan** (sesuai keputusan desain):
| Aksi | Kapan tersimpan permanen |
|---|---|
| Tambah mahasiswa baru (capture wajah) | **Langsung** saat "Selesaikan Pendaftaran" |
| Perbarui Dataset Wajah (capture ulang) | **Langsung** saat capture selesai |
| Edit NIM / Nama / Pindah Kelas | **Tertunda** — baru permanen setelah klik "UPLOAD KE PROGRAM" |
| Hapus Mahasiswa | **Tertunda** — baru permanen setelah klik "UPLOAD KE PROGRAM" |

Rasionalnya: aksi yang melibatkan kamera langsung (tambah baru, capture
ulang) bersifat live/tidak bisa "dibatalkan" secara natural, sedangkan
edit metadata & hapus adalah operasi yang aman untuk di-preview dulu
sebelum diterapkan permanen ke disk.

Saat **UPLOAD KE PROGRAM** ditekan: folder dataset dipindah/dihapus
sesuai perubahan, `EmbeddingDB` diperbarui (rename key NIM, update
field nama/kelas, atau hapus record) — embedding wajah itu sendiri
**tidak perlu dihitung ulang** untuk edit metadata biasa (hanya berubah
lewat re-capture dataset wajah).

### 4. Tingkat Akurasi Wajah
Dihitung otomatis setiap kali mahasiswa selesai didaftarkan/diperbarui
datasetnya — `recognition/similarity.py: compute_consistency_score()`
menghitung rata-rata cosine similarity antar-30 sample embedding yang
dicapture. Skor tinggi → wajah konsisten antar-capture → label "Bagus".
Threshold (`AppConfig.quality_good_threshold` / `quality_fair_threshold`)
bersifat heuristik — sebaiknya divalidasi ulang dengan data riil pada
eksperimen skripsi Anda.

### 5. Timer sesi & auto-stop
Saat waktu presensi habis (`AppConfig.duration` menit sejak sesi dibuka):
- Kamera otomatis dihentikan (`stop_camera()`)
- Panel menu berganti ke tampilan "⏰ Waktu Presensi Habis" dengan tombol
  **"Simpan & Tutup"**
- **Tidak** auto-save — dosen tetap harus menekan tombol untuk menyimpan
  riwayat presensi (sesuai keputusan desain: menghindari penyimpanan
  file tanpa konfirmasi eksplisit dari pengguna)

## Arsitektur & pembersihan kode

- `recognition/facenet_engine.py` — memakai arsitektur **non-blocking
  threading** (inference berjalan di background thread, main thread baca
  cache) sesuai update performa yang Anda berikan. MTCNN di-throttle
  setiap `DETECT_EVERY` frame, frame di-scale-down sebelum deteksi.
- Fitur v3 sebelumnya (multi-wajah per frame, dialog Presensi
  Manual/Gagalkan Presensi/Resume Materi/Presensi Asisten, status
  Hadir/Telat) **sengaja tidak dipertahankan** karena baseline kode yang
  Anda unggah sudah menyederhanakannya kembali ke deteksi 1 wajah per
  frame dengan arsitektur cache — perubahan pada update ini dibangun di
  atas baseline tersebut, bukan di atas v3.
- `utils.py`/`dialogs.py` versi lama dihapus (tidak lagi dipakai).

## Instalasi

```bash
pip install -r requirements.txt
python main.py
```

## Keterbatasan pengujian

Environment pengembangan tidak memiliki `tensorflow`, `keras-facenet`,
`mtcnn`, maupun `tkinter` terpasang (tanpa akses internet untuk
menginstal). Pengujian yang dilakukan:
- Seluruh file lolos `py_compile` (tidak ada syntax error)
- Logika inti diuji langsung terhadap dataset asli (bukan mock): pindah
  kelas (folder move + update `EmbeddingDB`), hapus mahasiswa (folder
  removal + hapus dari `EmbeddingDB`), deteksi kelas asing (logika
  perbandingan `student["class"] != AppConfig.class_code`) — semua
  diverifikasi bekerja benar sebelum dataset asli dikembalikan seperti semula.
- Smoke-test GUI penuh **tidak** bisa dijalankan di sini — **wajib**
  dijalankan langsung di komputer Anda (dengan kamera & dependensi
  lengkap) sebelum dipakai untuk demo/sidang.
