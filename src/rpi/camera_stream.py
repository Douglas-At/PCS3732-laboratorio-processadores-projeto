"""Servidor de vídeo da camada de borda (Raspberry Pi).

Expõe a câmera como um stream MJPEG via HTTP, no padrão descrito na
arquitetura (ver ``docs/diagramas/sequencia_streaming.d2``):

* ``GET /`` — página HTML mínima com ``<img src="/stream">``; o "dashboard" do
  computador central é o próprio navegador, sem programa extra só para assistir.
* ``GET /stream`` — resposta ``multipart/x-mixed-replace``; cada frame é um
  JPEG independente, com latência próxima a um período de frame.
* ``GET /control?var=quality&val=X`` — ajuste de qualidade (Módulo seguinte;
  o gancho ``FrameSource.set_quality`` já existe nos backends).

A captura fica isolada atrás da interface :class:`FrameSource` para permitir
trocar o backend sem redesenhar o servidor (RNF3):

* :class:`PiCameraSource` — módulo de câmera CSI via ``picamera2`` (primário).
* :class:`UsbCameraSource` — webcam USB via OpenCV/V4L2 (fallback).
* :class:`SyntheticSource` — frames gerados por software, para rodar e testar o
  pipe inteiro sem hardware (máquina de desenvolvimento).

:func:`make_source` escolhe o backend automaticamente na ordem CSI → USB →
sintético, então o mesmo arquivo roda no Pi e na máquina de dev.
"""

from __future__ import annotations

from io import BytesIO
from typing import Protocol

FPS = 15  # ponytail: limita CPU; calibrar no Raspberry Pi 3B+ real.
PORT = 5000


class FrameSource(Protocol):
    """Fonte de frames JPEG, independente do backend de captura."""

    def read_jpeg(self) -> bytes:
        """Retorna o frame atual já codificado em JPEG.

        Returns:
            Bytes do frame em JPEG, prontos para o corpo multipart.
        """
        ...

    def set_quality(self, value: int) -> None:
        """Ajusta a qualidade/compressão de captura.

        Args:
            value: Nível de qualidade (0–100) solicitado via ``GET /control``.
        """
        ...


class SyntheticSource:
    """Fonte de frames gerada por software, sem câmera.

    Desenha um relógio e um contador que avançam a cada leitura, de modo que o
    stream fique visivelmente "ao vivo" na máquina de desenvolvimento.
    """

    def __init__(self, size: tuple[int, int] = (640, 480)) -> None:
        self._size = size
        self._quality = 75
        self._count = 0

    def read_jpeg(self) -> bytes:
        from datetime import datetime

        from PIL import Image, ImageDraw

        self._count += 1
        img = Image.new("RGB", self._size, (20, 20, 30))
        draw = ImageDraw.Draw(img)
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        draw.text((20, 20), "SyntheticSource (sem camera)", fill=(230, 230, 230))
        draw.text((20, 50), now, fill=(120, 220, 120))
        draw.text((20, 80), f"frame #{self._count}", fill=(220, 220, 120))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=self._quality)
        return buf.getvalue()

    def set_quality(self, value: int) -> None:
        self._quality = max(1, min(100, int(value)))


class UsbCameraSource:
    """Webcam USB via OpenCV/V4L2 (fallback quando não há módulo CSI)."""

    def __init__(self, index: int = 0) -> None:
        import cv2

        self._cv2 = cv2
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Câmera USB não encontrada no índice {index}")
        self._quality = 75

    def read_jpeg(self) -> bytes:
        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError("Falha ao ler frame da câmera USB")
        params = [self._cv2.IMWRITE_JPEG_QUALITY, self._quality]
        ok, buf = self._cv2.imencode(".jpg", frame, params)
        if not ok:
            raise RuntimeError("Falha ao codificar frame em JPEG")
        return buf.tobytes()

    def set_quality(self, value: int) -> None:
        self._quality = max(1, min(100, int(value)))


class PiCameraSource:
    """Módulo de câmera CSI via ``picamera2`` (backend primário no Pi)."""

    def __init__(self, size: tuple[int, int] = (640, 480)) -> None:
        from picamera2 import Picamera2

        self._cam = Picamera2()
        self._cam.configure(
            self._cam.create_video_configuration(main={"size": size})
        )
        self._cam.start()
        self._quality = 75

    def read_jpeg(self) -> bytes:
        buf = BytesIO()
        # picamera2 aplica o nível de qualidade JPEG configurado nas options.
        self._cam.options["quality"] = self._quality
        self._cam.capture_file(buf, format="jpeg")
        return buf.getvalue()

    def set_quality(self, value: int) -> None:
        self._quality = max(1, min(100, int(value)))


def make_source() -> FrameSource:
    """Escolhe o backend disponível: CSI → USB → sintético.

    Returns:
        A primeira :class:`FrameSource` que inicializar sem erro. Assim o mesmo
        arquivo roda no Pi (câmera real) e na máquina de dev (sintético).
    """
    for factory in (PiCameraSource, UsbCameraSource, SyntheticSource):
        try:
            source = factory()
            print(f"[camera_stream] backend: {factory.__name__}")
            return source
        except Exception as exc:  # ImportError, RuntimeError de hardware ausente
            print(f"[camera_stream] {factory.__name__} indisponível: {exc}")
    raise RuntimeError("Nenhum backend de câmera disponível")


def mjpeg_frame(jpeg: bytes) -> bytes:
    """Monta um chunk multipart (boundary ``frame``) para um frame JPEG.

    Função pura (sem Flask) para poder ser testada sem subir o servidor.
    """
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
        + jpeg + b"\r\n"
    )


def create_app(source: FrameSource):
    """Cria a aplicação Flask que serve a página e o stream MJPEG.

    Flask é importado localmente para o módulo poder ser importado (e testado)
    sem Flask instalado na máquina de desenvolvimento.
    """
    import time

    from flask import Flask, Response

    app = Flask(__name__)

    @app.route("/")
    def index():
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Porteiro — vídeo</title></head>"
            "<body style='margin:0;background:#111'>"
            "<img src='/stream' style='width:100%;height:auto'>"
            "</body></html>"
        )

    @app.route("/stream")
    def stream():
        def gen():
            while True:
                yield mjpeg_frame(source.read_jpeg())
                time.sleep(1 / FPS)

        return Response(
            gen(), mimetype="multipart/x-mixed-replace; boundary=frame"
        )

    return app


def main() -> None:
    """Sobe o servidor de vídeo em ``0.0.0.0:PORT`` (visível na rede local)."""
    app = create_app(make_source())
    # threaded=True: o /stream mantém a conexão aberta; sem isso, / e /control
    # ficariam bloqueados enquanto alguém assiste.
    app.run(host="0.0.0.0", port=PORT, threaded=True)


if __name__ == "__main__":
    main()
