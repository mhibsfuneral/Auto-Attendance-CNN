"""
facenet_engine.py — Optimized (threading + MTCNN throttling)

Arsitektur sebelumnya (blocking):
  Main thread → get_frame() → MTCNN(~150ms) + FaceNet(~50ms) → display
  Hasil: 4-7 FPS karena setiap frame nunggu inference.

Arsitektur baru (non-blocking):
  Inference thread → terus jalan di background, simpan hasil terakhir
  Main thread     → get_frame() cukup baca cache → display 25-30 FPS

Optimasi tambahan:
  1. MTCNN throttled setiap DETECT_EVERY frames (bukan tiap frame)
  2. Frame di-scale down sebelum MTCNN, koordinat di-scale balik
  3. FaceNet hanya di-crop wajah (160×160), bukan full frame
  4. Hasil annotasi disiapkan di thread, main thread tinggal pakai
"""

import threading
import time
import cv2
import numpy as np
from mtcnn import MTCNN
from keras_facenet import FaceNet

from config import AppConfig
from recognition.embedding_db import EmbeddingDB
from recognition.similarity import cosine_similarity


class FaceNetEngine:

    # ── Tunable constants ──────────────────────────────────────────
    # Jalankan MTCNN setiap N frame inference.
    # Lebih besar → MTCNN lebih jarang → lebih cepat, tapi box sedikit
    # lag saat wajah baru masuk. Nilai 3-4 adalah sweet spot.
    DETECT_EVERY: int = 4

    # Scale frame sebelum MTCNN. 0.6 = 60% ukuran asli.
    # Lebih kecil → MTCNN lebih cepat, tapi akurasi deteksi sedikit turun.
    DETECT_SCALE: float = 0.6
    # ──────────────────────────────────────────────────────────────

    def __init__(self):
        self.cap = None
        self.detector = None
        self.embedder = None
        self.models_loaded = False

        self.db = EmbeddingDB()
        self.embeddings = self.db.load()

        self.threshold = AppConfig.similarity_threshold
        self.cooldown  = AppConfig.attendance_cooldown
        self.last_seen: dict = {}

        # Threading
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Shared state (ditulis inference thread, dibaca main thread)
        self._cached_frame: np.ndarray | None = None
        self._cached_student: dict | None = None
        self._cached_conf: float | None = None

    # ── Model loading ──────────────────────────────────────────────

    def load_models(self):
        if self.models_loaded:
            return
        print("Loading FaceNet...")
        self.embedder = FaceNet()
        print("Loading MTCNN...")
        self.detector = MTCNN()
        self.models_loaded = True
        print("Models ready.")

    def reload_database(self):
        self.embeddings = self.db.load()

    # ── Camera lifecycle ───────────────────────────────────────────

    def start_camera(self) -> bool:
        if not self.models_loaded:
            self.load_models()

        self.cap = cv2.VideoCapture(AppConfig.camera_index)
        if not self.cap.isOpened():
            return False

        # Set buffer kecil supaya frame tidak antri (pakai frame terbaru)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._running = True
        self._thread = threading.Thread(
            target=self._inference_loop,
            daemon=True,
            name="FaceNetInference"
        )
        self._thread.start()
        return True

    def stop_camera(self):
        self._running = False
        if self.cap:
            self.cap.release()
            self.cap = None

    # ── Inference loop (background thread) ────────────────────────

    def _inference_loop(self):
        """
        Berjalan terus di background thread.
        - Baca frame dari kamera secepat mungkin.
        - MTCNN setiap DETECT_EVERY frame (throttled).
        - FaceNet setiap frame jika ada wajah (di-crop, cepat).
        - Simpan hasil annotasi ke shared state.
        """
        detect_counter = 0
        cached_boxes: list[tuple[int, int, int, int]] = []

        while self._running:
            if not self.cap:
                break

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            detect_counter += 1
            h_orig, w_orig = frame.shape[:2]

            # ── 1. Deteksi wajah (MTCNN, throttled) ───────────────
            if detect_counter >= self.DETECT_EVERY:
                detect_counter = 0

                # Scale down untuk kecepatan
                small = cv2.resize(
                    frame, (0, 0),
                    fx=self.DETECT_SCALE,
                    fy=self.DETECT_SCALE
                )
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

                try:
                    faces = self.detector.detect_faces(rgb_small)
                except Exception:
                    faces = []

                # Scale koordinat balik ke ukuran asli
                inv = 1.0 / self.DETECT_SCALE
                cached_boxes = []
                for f in faces:
                    x, y, w, h = f["box"]
                    x = max(0, int(x * inv))
                    y = max(0, int(y * inv))
                    w = min(int(w * inv), w_orig - x)
                    h = min(int(h * inv), h_orig - y)
                    if w > 10 and h > 10:   # filter kotak sangat kecil
                        cached_boxes.append((x, y, w, h))

            # ── 2. Anotasi & pengenalan ────────────────────────────
            annotated = frame.copy()
            student_found: dict | None = None
            conf_found: float | None = None

            if cached_boxes:
                # Hanya proses wajah pertama (paling menonjol)
                x, y, w, h = cached_boxes[0]

                # FaceNet pada crop wajah saja (160×160) — jauh lebih cepat
                crop = frame[y:y + h, x:x + w]
                if crop.size > 0:
                    try:
                        rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                        rgb_160  = cv2.resize(rgb_crop, (160, 160))
                        emb = self.embedder.embeddings([rgb_160])[0]
                        student_found, conf_found = self._match(emb)
                    except Exception:
                        student_found, conf_found = None, None

                # Gambar bounding box + label
                if student_found:
                    label = f'{student_found["name"]} ({conf_found:.2f})'
                    color = (0, 255, 0)
                elif conf_found is not None:
                    label = f"Unknown ({conf_found:.2f})"
                    color = (0, 50, 255)
                else:
                    label = "Unknown"
                    color = (0, 50, 255)

                cv2.rectangle(
                    annotated,
                    (x, y), (x + w, y + h),
                    color, 2
                )
                cv2.putText(
                    annotated, label,
                    (x, max(y - 10, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75, color, 2,
                    cv2.LINE_AA
                )

                # Gambar kotak tambahan jika ada lebih dari 1 wajah
                for (bx, by, bw, bh) in cached_boxes[1:]:
                    cv2.rectangle(
                        annotated,
                        (bx, by), (bx + bw, by + bh),
                        (200, 200, 0), 1
                    )

            # ── 3. Tulis ke shared state ───────────────────────────
            with self._lock:
                self._cached_frame   = annotated
                self._cached_student = student_found
                self._cached_conf    = conf_found

    # ── Public API (dipanggil main/Tkinter thread) ─────────────────

    def get_frame(self):
        """
        Non-blocking — langsung kembalikan frame & hasil terakhir dari cache.
        Main thread memanggil ini di setiap tick (~33ms), tanpa perlu nunggu
        inference selesai.
        """
        with self._lock:
            frame   = self._cached_frame
            student = self._cached_student
            conf    = self._cached_conf
        return frame, student, conf

    def is_in_cooldown(self, nim: str) -> bool:
        now = time.time()
        if nim not in self.last_seen:
            self.last_seen[nim] = now
            return False
        elapsed = now - self.last_seen[nim]
        if elapsed < self.cooldown:
            return True
        self.last_seen[nim] = now
        return False

    # ── Helpers ────────────────────────────────────────────────────

    def _match(self, embedding: np.ndarray):
        if not self.embeddings:
            return None, None

        best       = None
        best_score = -1.0

        for _, student in self.embeddings.items():
            score = cosine_similarity(embedding, np.array(student["embedding"]))
            if score > best_score:
                best_score = score
                best       = student

        if best_score >= self.threshold:
            return best, float(best_score)
        return None, float(best_score)

    def preprocess_face(self, face: np.ndarray) -> np.ndarray:
        face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        face = cv2.resize(face, (160, 160))
        return face.astype("float32")

    def get_embedding(self, face: np.ndarray) -> np.ndarray:
        """Untuk registrasi: ekstrak embedding dari crop wajah."""
        if self.embedder is None:
            self.embedder = FaceNet()
        processed = self.preprocess_face(face)
        return self.embedder.embeddings([processed])[0]
