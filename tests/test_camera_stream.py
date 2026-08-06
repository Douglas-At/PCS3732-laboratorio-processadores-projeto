"""Checagem executável do Módulo 1 (streaming da câmera).

Roda sem pytest, sem Flask e sem câmera:

    python tests/test_camera_stream.py

Cobre RF1 (frame JPEG válido do pipe de streaming) e RNF3 (backend sintético
plugável, sem hardware). Requer apenas Pillow (``pip install pillow``).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "rpi"))

from camera_stream import SyntheticSource, mjpeg_frame  # noqa: E402


def test_synthetic_source_gera_jpeg_valido():
    jpeg = SyntheticSource().read_jpeg()
    assert jpeg[:2] == b"\xff\xd8", "JPEG deve começar com SOI (FFD8)"
    assert jpeg[-2:] == b"\xff\xd9", "JPEG deve terminar com EOI (FFD9)"


def test_frames_avancam_provando_liveness():
    src = SyntheticSource()
    a = src.read_jpeg()
    b = src.read_jpeg()
    assert a != b, "frames consecutivos devem diferir (contador/relógio)"


def test_mjpeg_frame_monta_chunk_multipart():
    chunk = mjpeg_frame(b"x")
    assert b"--frame" in chunk
    assert b"Content-Type: image/jpeg" in chunk
    assert chunk.endswith(b"\r\n")


def test_overlay_com_angulo_mantem_jpeg_valido():
    # Overlay (horário + ângulo do joystick) desenhado sem quebrar o JPEG.
    jpeg = SyntheticSource(get_angle=lambda: 42.0).read_jpeg()
    assert jpeg[:2] == b"\xff\xd8", "JPEG deve começar com SOI (FFD8)"
    assert jpeg[-2:] == b"\xff\xd9", "JPEG deve terminar com EOI (FFD9)"


def test_save_clip_sem_buffer_retorna_none():
    # Salvar 10 s só existe na câmera CSI do Pi; no sintético, sem suporte.
    assert SyntheticSource().save_clip("clips/x") is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("todos os testes passaram")
