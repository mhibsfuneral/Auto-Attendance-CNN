class AppConfig:
    # Session info
    lecturer_name = ""
    class_code = ""
    room = ""
    duration = 0

    # Recognition
    recognition_method = "cnn_facenet"

    # Camera
    camera_index = 0

    # Paths
    dataset_dir = "dataset"
    attendance_csv = "attendance.csv"
    embeddings_path = "models/embeddings.pkl"
    classes_path = "models/classes.json"

    # Registration
    total_capture_images = 30
    # Jeda antar capture (detik) — diperpanjang dari 0.4s agar mahasiswa
    # sempat menggerakkan kepala sedikit antar foto (variasi pose & cahaya),
    # sehingga rata-rata embedding yang dihasilkan lebih representatif.
    capture_interval_seconds = 0.7

    # Face Recognition Settings (FaceNet — cosine similarity)
    # similarity = kemiripan antara embedding wajah & data training ->
    # semakin BESAR semakin mirip (rentang -1.0 s.d. 1.0).
    similarity_threshold = 0.78
    attendance_cooldown = 5

    # Tingkat Akurasi Wajah — dihitung dari rata-rata cosine similarity
    # antar-sample embedding yang dicapture saat registrasi (konsistensi
    # wajah mahasiswa tsb terhadap dirinya sendiri). Threshold ini heuristik;
    # sesuaikan berdasarkan data riil pada eksperimen skripsi Anda.
    quality_good_threshold = 0.90     # >= ini -> "Bagus"
    quality_fair_threshold = 0.75     # >= ini -> "Cukup", di bawahnya -> "Kurang"

    # Face Detection
    detector = "mtcnn"   # MTCNN (deep learning detector, akurat untuk berbagai sudut wajah)
