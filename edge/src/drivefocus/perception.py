"""Tầng cảm biến trên PC: MediaPipe Face Landmarker + Hand Landmarker -> FrameObs.

Mạng nơ-ron ở đây chỉ là CẢM BIẾN phổ thông (tìm mặt, điểm mốc, bàn tay). Mọi quyết định
nằm ở engine. Trên K230, lớp này được thay bằng các mô hình trong SDK (face_landmark,
face_pose, phát hiện lòng bàn tay) mà tầng quyết định không đổi.

Chỉ số điểm mốc MediaPipe (478 điểm, có mống mắt):
- mắt: [33,133,160,144,158,153] và [362,263,385,380,387,373] (cùng bộ với
  e-candeloro/driver-state-detection, thứ tự: hai khóe, cặp trên/dưới thứ nhất, cặp thứ hai)
- môi trong: 13 (trên), 14 (dưới); khóe miệng: 78, 308
- mống mắt: 468 và 473; mép mặt gần tai: 234, 454
- PnP: mũi 1, cằm 152, khóe mắt ngoài 33 và 263, khóe miệng 61 và 291
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from . import geometry as geo
from .config import Cfg
from .types import FrameObs

EYE_A = [33, 133, 160, 144, 158, 153]
EYE_B = [362, 263, 385, 380, 387, 373]
IRIS_A, IRIS_B = 468, 473
MOUTH_UP, MOUTH_LOW, MOUTH_L, MOUTH_R = 13, 14, 78, 308
EDGE_A, EDGE_B = 234, 454
CHEEK_A, CHEEK_B = 205, 425
PNP_IDX = [1, 152, 33, 263, 61, 291]


@dataclass
class Debug:
    """Dữ liệu để vẽ lên màn hình, không dùng để quyết định."""
    eye_pts: list = field(default_factory=list)
    mouth_pts: list = field(default_factory=list)
    hand_centers: list = field(default_factory=list)
    face_box: Optional[tuple] = None
    all_pts: list = field(default_factory=list)   # toàn bộ điểm mốc, để vẽ chế độ riêng tư


class MediaPipeSensor:
    def __init__(self, cfg: Cfg, models_dir: str | Path, pose_method: str = "matrix", image_mode: bool = False):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self.mp = mp
        self.pose_method = pose_method
        self.image_mode = image_mode
        mode = vision.RunningMode.IMAGE if image_mode else vision.RunningMode.VIDEO
        self.o = cfg.observation
        d = Path(models_dir)
        self.face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(d / "face_landmarker.task")),
            running_mode=mode, num_faces=1,
            output_facial_transformation_matrixes=True,
            min_face_detection_confidence=0.5, min_face_presence_confidence=0.5, min_tracking_confidence=0.5))
        self.hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(d / "hand_landmarker.task")),
            running_mode=mode, num_hands=2))
        self._last_ms = -1

    def close(self) -> None:
        self.face.close()
        self.hands.close()

    def _ms(self, t: float) -> int:
        ms = max(self._last_ms + 1, int(t * 1000))   # MediaPipe yêu cầu mốc thời gian tăng chặt
        self._last_ms = ms
        return ms

    def process(self, frame_bgr: np.ndarray, t: float) -> tuple[FrameObs, Debug]:
        import cv2

        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        if self.image_mode:                       # ảnh rời: không theo dõi giữa các khung
            fres = self.face.detect(image)
            hres = self.hands.detect(image)
        else:
            ms = self._ms(t)
            fres = self.face.detect_for_video(image, ms)
            hres = self.hands.detect_for_video(image, ms)
        return self.observe(frame_bgr, t, fres, hres)

    def observe(self, frame_bgr: np.ndarray, t: float, fres, hres) -> tuple[FrameObs, Debug]:
        h, w = frame_bgr.shape[:2]
        dbg = Debug()
        if not fres.face_landmarks:
            return FrameObs(t=t, face=False), dbg

        lm = np.array([(p.x * w, p.y * h) for p in fres.face_landmarks[0]], dtype=np.float64)
        n = len(lm)
        has_iris = n >= 478

        ear_a = geo.eye_aspect_ratio(lm[EYE_A])
        ear_b = geo.eye_aspect_ratio(lm[EYE_B])
        ear = geo.mean_ear(ear_a, ear_b)
        observable = self._eyes_observable(frame_bgr, lm, ear)
        mar = geo.mouth_aspect_ratio(lm[MOUTH_UP], lm[MOUTH_LOW], lm[MOUTH_L], lm[MOUTH_R])

        pose = None
        mats = getattr(fres, "facial_transformation_matrixes", None)
        if self.pose_method == "matrix" and mats:
            pose = geo.pose_from_mediapipe_matrix(np.array(mats[0]))
        if pose is None:
            pose = geo.head_pose(lm[PNP_IDX], w, h)
        yaw, pitch, roll = pose if pose else (None, None, None)

        gaze = self._gaze(lm) if has_iris else None

        face_w = float(np.linalg.norm(lm[EDGE_A] - lm[EDGE_B]))
        hand_ear = hand_mouth = hand_eye = None
        centers = []
        if hres is not None and hres.hand_landmarks and face_w > 1:
            mouth = (lm[MOUTH_UP] + lm[MOUTH_LOW]) / 2.0
            eyes_mid = (lm[EYE_A[0]] + lm[EYE_B[1]]) / 2.0
            for hand in hres.hand_landmarks:
                c = np.mean([(p.x * w, p.y * h) for p in hand], axis=0)
                centers.append(tuple(c))
                d_ear = min(np.linalg.norm(c - lm[EDGE_A]), np.linalg.norm(c - lm[EDGE_B])) / face_w
                d_mouth = np.linalg.norm(c - mouth) / face_w
                d_eye = np.linalg.norm(c - eyes_mid) / face_w
                hand_ear = d_ear if hand_ear is None else min(hand_ear, d_ear)
                hand_mouth = d_mouth if hand_mouth is None else min(hand_mouth, d_mouth)
                hand_eye = d_eye if hand_eye is None else min(hand_eye, d_eye)

        dbg.eye_pts = [tuple(lm[i]) for i in EYE_A + EYE_B]
        dbg.mouth_pts = [tuple(lm[i]) for i in (MOUTH_UP, MOUTH_LOW, MOUTH_L, MOUTH_R)]
        dbg.hand_centers = centers
        dbg.all_pts = [tuple(q) for q in lm[:468]]
        dbg.face_box = (float(lm[:, 0].min()), float(lm[:, 1].min()), float(lm[:, 0].max()), float(lm[:, 1].max()))
        obs = FrameObs(
            t=t, face=True, ear=ear, eyes_observable=observable, mar=mar,
            yaw=yaw, pitch=pitch, roll=roll, gaze=gaze,
            hand_ear=None if hand_ear is None else float(hand_ear),
            hand_mouth=None if hand_mouth is None else float(hand_mouth),
            hand_eye=None if hand_eye is None else float(hand_eye),
            hands_visible=bool(centers),
        )
        return obs, dbg

    # ------------------------------------------------------------------ nội bộ
    def _eyes_observable(self, frame_bgr: np.ndarray, lm: np.ndarray, ear: Optional[float]) -> bool:
        """Mắt có đủ rõ để tin EAR không.

        Không dùng độ tương phản vùng mắt: mi mắt nhắm là vùng da phẳng và phải vẫn được coi là
        QUAN SÁT ĐƯỢC (nếu không, nhắm mắt sẽ biến thành KHÔNG BIẾT và không bao giờ báo).
        Phân biệt kính râm / thiếu sáng bằng độ TỐI: vùng mắt tối hơn nhiều so với da má.
        Giới hạn đã biết: kính râm phản chiếu (tráng gương) sáng nên không bị phát hiện bằng cách này.
        """
        import cv2

        if ear is None:
            return False
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        def patch_mean(cx: float, cy: float, r: int = 6) -> float:
            x, y = int(cx), int(cy)
            roi = gray[max(0, y - r):min(h, y + r), max(0, x - r):min(w, x + r)]
            return float(roi.mean()) if roi.size else 0.0

        skin = float(np.mean([patch_mean(*lm[CHEEK_A]), patch_mean(*lm[CHEEK_B])]))
        for idx in (EYE_A, EYE_B):
            pts = lm[idx]
            if float(np.linalg.norm(pts[0] - pts[1])) < self.o.min_eye_width_px:
                return False
            x0, y0 = np.floor(pts.min(axis=0)).astype(int)
            x1, y1 = np.ceil(pts.max(axis=0)).astype(int)
            roi = gray[max(0, y0):min(h, y1 + 1), max(0, x0):min(w, x1 + 1)]
            if roi.size == 0:
                return False
            m = float(roi.mean())
            if m < self.o.eye_min_brightness or (skin > 0 and m < self.o.eye_dark_ratio * skin):
                return False
        return True

    @staticmethod
    def _gaze(lm: np.ndarray) -> Optional[float]:
        scores = []
        for eye, iris in ((EYE_A, IRIS_A), (EYE_B, IRIS_B)):
            pts = lm[eye]
            x0, y0 = pts.min(axis=0)
            x1, y1 = pts.max(axis=0)
            width = x1 - x0
            if width < 1e-6:
                continue
            centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
            scores.append(float(np.linalg.norm(lm[iris] - centre) / width))
        return float(np.mean(scores)) if scores else None
