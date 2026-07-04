import numpy as np


def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)

    denominator = np.linalg.norm(vec1) * np.linalg.norm(vec2)

    if denominator == 0:
        return 0.0

    similarity = np.dot(vec1, vec2) / denominator
    return float(similarity)


def compute_consistency_score(embeddings):
    """Hitung skor konsistensi wajah dari kumpulan embedding sample (mis.
    30 embedding hasil capture saat registrasi) — rata-rata cosine
    similarity antar semua pasangan sample.

    Skor tinggi (mendekati 1.0) berarti wajah yang tercapture konsisten
    satu sama lain (registrasi bagus, pencahayaan stabil, pose tidak
    terlalu ekstrem berbeda-beda). Skor rendah bisa menandakan capture
    kurang stabil (mis. pergerakan berlebihan, pencahayaan berubah-ubah).
    """
    n = len(embeddings)
    if n < 2:
        return 1.0

    scores = []
    for i in range(n):
        for j in range(i + 1, n):
            scores.append(cosine_similarity(embeddings[i], embeddings[j]))

    return float(np.mean(scores)) if scores else 1.0


def quality_label_from_score(score, good_threshold, fair_threshold):
    """Konversi skor konsistensi numerik menjadi label kategorikal yang
    ditampilkan di UI Manajer Mahasiswa ("Tingkat Akurasi Wajah")."""
    if score >= good_threshold:
        return "Bagus"
    if score >= fair_threshold:
        return "Cukup"
    return "Kurang"