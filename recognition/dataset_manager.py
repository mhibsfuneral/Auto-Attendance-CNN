import os
import cv2
import time
from mtcnn import MTCNN
from config import AppConfig


class DatasetManager:
    def __init__(self):
        self.cap = None
        self.capture_count = 0
        self.current_student_dir = None

        self.last_capture_time = 0
        self.max_capture = AppConfig.total_capture_images

        self.detector = MTCNN()

    def create_student_folder(self, nim, nama, kelas):
        student_folder = f"{nim}_{nama}".replace(" ", "_")
        path = os.path.join(AppConfig.dataset_dir, kelas, student_folder)

        os.makedirs(path, exist_ok=True)

        self.current_student_dir = path
        self.capture_count = 0

        return path

    def start_camera(self):
        self.cap = cv2.VideoCapture(AppConfig.camera_index)
        return self.cap.isOpened()

    def stop_camera(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def get_frame(self):
        if not self.cap:
            return None, False

        ret, frame = self.cap.read()
        if not ret:
            return None, False

        return frame, True

    def detect_and_save_face(self, frame):
        """
        Detect faces in frame using MTCNN, draw bounding boxes, and save
        one face crop per call (throttled to 0.4 s between captures).

        Returns:
            frame       — annotated frame (bounding box drawn)
            saved       — True if a face was saved this call
            saved_path  — path of the saved file, or None
            face_crop   — the BGR face crop that was saved, or None
                          (FIX: previously callers tried to re-detect via a
                          Haar cascade that was never initialised; returning
                          the crop here eliminates that need entirely)
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = self.detector.detect_faces(rgb_frame)

        saved = False
        saved_path = None
        face_crop = None  # FIX: return the crop so callers don't need to re-detect

        for face_data in faces:
            x, y, w, h = face_data["box"]

            x = max(0, x)
            y = max(0, y)

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

            if self.capture_count < self.max_capture:
                current_time = time.time()

                if current_time - self.last_capture_time >= 0.4:
                    crop = frame[y:y + h, x:x + w]

                    if crop.size == 0:
                        continue

                    filename = f"{self.capture_count + 1}.jpg"
                    filepath = os.path.join(
                        self.current_student_dir,
                        filename
                    )

                    cv2.imwrite(filepath, crop)

                    self.capture_count += 1
                    self.last_capture_time = current_time
                    saved = True
                    saved_path = filepath
                    face_crop = crop  # FIX: capture here, return below

            break  # only process the first detected face

        return frame, saved, saved_path, face_crop  # FIX: added face_crop

    def is_complete(self):
        return self.capture_count >= AppConfig.total_capture_images
