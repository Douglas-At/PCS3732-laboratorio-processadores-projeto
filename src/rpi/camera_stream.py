"""Servidor de vídeo da camada de borda (Raspberry Pi) — interface de porteiro.

Expõe a câmera como um stream MJPEG via HTTP, no padrão descrito na
arquitetura (ver ``docs/diagramas/sequencia_streaming.d2``):

* ``GET /`` — página HTML do porteiro: ``<img src="/stream">`` + botão para
  salvar os últimos 10 s. O "dashboard" do computador central é o próprio
  navegador, sem programa extra só para assistir.
* ``GET /stream`` — resposta ``multipart/x-mixed-replace``; cada frame é um
  JPEG independente, com latência próxima a um período de frame.
* ``POST /save`` — grava os últimos ~10 s de vídeo (só na câmera CSI do Pi).
* ``GET /control?var=quality&val=X`` — ajuste de qualidade (gancho já previsto).

Cada frame leva **queimado** o horário atual e o **ângulo da câmera** (o servo
é panorado pelo joystick — ver ``joystick_servo.py``). Assim o horário e o
ângulo aparecem tanto no vídeo ao vivo quanto no clipe salvo.

A captura fica isolada atrás da interface :class:`FrameSource` para permitir
trocar o backend sem redesenhar o servidor (RNF3):

* :class:`PiCameraSource` — módulo de câmera CSI via ``picamera2`` (primário);
  faz o overlay no ``pre_callback`` e mantém um buffer circular H264 dos
  últimos 10 s (recurso de salvar, exclusivo do Pi).
* :class:`UsbCameraSource` — webcam USB via OpenCV/V4L2 (fallback).
* :class:`SyntheticSource` — frames gerados por software, para rodar e testar o
  pipe inteiro sem hardware (máquina de desenvolvimento).

:func:`make_source` escolhe o backend automaticamente na ordem CSI → USB →
sintético, então o mesmo arquivo roda no Pi e na máquina de dev.
"""

from __future__ import annotations

from datetime import datetime
from io import BufferedIOBase, BytesIO
from typing import Callable, Optional, Protocol

FPS = 15  
PORT = 5000
BUFFER_SEGUNDOS = 10  # janela do "salvar últimos N s"


def _overlay_linhas(angulo: float) -> tuple[str, str]:
    """Duas linhas de overlay: horário atual e ângulo da câmera."""
    return datetime.now().strftime("%H:%M:%S"), f"ang: {angulo:3.0f} g"


def _desenhar_cv2(cv2, arr, angulo: float, alarme: bool) -> None:
    """Queima horário + ângulo (e o alerta de intruso) num array BGR (cv2)."""
    fonte = cv2.FONT_HERSHEY_SIMPLEX
    hora, ang = _overlay_linhas(angulo)
    cv2.putText(arr, hora, (20, 40), fonte, 1, (0, 255, 0), 2)
    cv2.putText(arr, ang, (20, 80), fonte, 1, (0, 255, 255), 2)
    if alarme:
        # BGR: (0,0,255) = vermelho.
        cv2.putText(arr, "INTRUSO DETECTADO", (20, 150), fonte, 1.1, (0, 0, 255), 3)
        cv2.putText(arr, "CHAMANDO A POLICIA", (20, 195), fonte, 1.1, (0, 0, 255), 3)


class FrameSource(Protocol):
    """Fonte de frames JPEG, independente do backend de captura."""

    def read_jpeg(self) -> bytes:
        """Retorna o frame atual já codificado em JPEG (com overlay)."""
        ...

    def set_quality(self, value: int) -> None:
        """Ajusta a qualidade/compressão de captura (0–100)."""
        ...

    def save_clip(self, path_base: str) -> Optional[str]:
        """Grava os últimos ~10 s de vídeo.

        Args:
            path_base: Caminho de saída sem extensão (o backend escolhe).

        Returns:
            Caminho do arquivo gravado, ou ``None`` se o backend não suportar
            (só a câmera CSI do Pi mantém o buffer circular).
        """
        ...


class SyntheticSource:
    """Fonte de frames gerada por software, sem câmera.

    Desenha o overlay (relógio + ângulo) e um contador que avança a cada
    leitura, de modo que o stream fique visivelmente "ao vivo" na máquina de
    desenvolvimento.
    """

    def __init__(
        self,
        size: tuple[int, int] = (640, 480),
        get_angle: Optional[Callable[[], float]] = None,
        get_alarme: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._size = size
        self._quality = 75
        self._count = 0
        self._get_angle = get_angle or (lambda: float(90))
        self._get_alarme = get_alarme or (lambda: False)

    def read_jpeg(self) -> bytes:
        from PIL import Image, ImageDraw

        self._count += 1
        img = Image.new("RGB", self._size, (20, 20, 30))
        draw = ImageDraw.Draw(img)
        hora, ang = _overlay_linhas(self._get_angle())
        draw.text((20, 20), "Porteiro (sem camera)", fill=(230, 230, 230))
        draw.text((20, 50), hora, fill=(120, 220, 120))
        draw.text((20, 80), ang, fill=(220, 220, 120))
        draw.text((20, 110), f"frame #{self._count}", fill=(150, 150, 150))
        if self._get_alarme():
            draw.text((20, 150), "INTRUSO DETECTADO", fill=(255, 0, 0))
            draw.text((20, 170), "CHAMANDO A POLICIA", fill=(255, 0, 0))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=self._quality)
        return buf.getvalue()

    def set_quality(self, value: int) -> None:
        self._quality = max(1, min(100, int(value)))

    def save_clip(self, path_base: str) -> Optional[str]:
        return None  # buffer circular é recurso da câmera CSI (Pi)


class UsbCameraSource:
    """Webcam USB via OpenCV/V4L2 (fallback quando não há módulo CSI)."""

    def __init__(
        self,
        index: int = 0,
        get_angle: Optional[Callable[[], float]] = None,
        get_alarme: Optional[Callable[[], bool]] = None,
    ) -> None:
        import cv2

        self._cv2 = cv2
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Câmera USB não encontrada no índice {index}")
        self._quality = 75
        self._get_angle = get_angle or (lambda: float(90))
        self._get_alarme = get_alarme or (lambda: False)

    def read_jpeg(self) -> bytes:
        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError("Falha ao ler frame da câmera USB")
        cv2 = self._cv2
        _desenhar_cv2(cv2, frame, self._get_angle(), self._get_alarme())
        params = [cv2.IMWRITE_JPEG_QUALITY, self._quality]
        ok, buf = cv2.imencode(".jpg", frame, params)
        if not ok:
            raise RuntimeError("Falha ao codificar frame em JPEG")
        return buf.tobytes()

    def set_quality(self, value: int) -> None:
        self._quality = max(1, min(100, int(value)))

    def save_clip(self, path_base: str) -> Optional[str]:
        return None  # sem buffer circular no backend USB


class _StreamingOutput(BufferedIOBase):
    """Buffer de "último frame" para o JpegEncoder do picamera2.

    Padrão do exemplo oficial ``mjpeg_server.py``: o encoder chama ``write``
    a cada frame; ``read_jpeg`` espera o próximo e o devolve. Precisa herdar
    ``io.BufferedIOBase`` — o ``FileOutput`` do picamera2 exige isso.
    """

    def __init__(self) -> None:
        import threading

        self.frame: Optional[bytes] = None
        self.condition = threading.Condition()

    def write(self, buf: bytes) -> None:
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class PiCameraSource:
    """Módulo de câmera CSI via ``picamera2`` (backend primário no Pi).

    Roda dois encoders sobre o mesmo stream: ``JpegEncoder`` alimenta o MJPEG
    e ``H264Encoder`` alimenta um ``CircularOutput`` com os últimos ~10 s. O
    overlay (horário + ângulo) é desenhado no ``pre_callback``, então entra
    tanto no stream quanto no clipe salvo.
    """

    def __init__(
        self,
        size: tuple[int, int] = (640, 480),
        get_angle: Optional[Callable[[], float]] = None,
        get_alarme: Optional[Callable[[], bool]] = None,
    ) -> None:
        import cv2
        from picamera2 import MappedArray, Picamera2
        from picamera2.encoders import H264Encoder, JpegEncoder
        from picamera2.outputs import CircularOutput, FileOutput

        self._cv2 = cv2
        self._MappedArray = MappedArray
        self._get_angle = get_angle or (lambda: float(90))
        self._get_alarme = get_alarme or (lambda: False)

        self._cam = Picamera2()
        self._cam.configure(
            self._cam.create_video_configuration(
                main={"size": size}, controls={"FrameRate": FPS}
            )
        )
        self._cam.pre_callback = self._desenhar_overlay

        self._stream = _StreamingOutput()
        # pode fugir do FPS nominal). Alvo: BUFFER_SEGUNDOS de vídeo.
        self._circular = CircularOutput(buffersize=BUFFER_SEGUNDOS * FPS)
        self._cam.start_encoder(JpegEncoder(), FileOutput(self._stream))
        self._cam.start_encoder(H264Encoder(), self._circular)
        self._cam.start()

    def _desenhar_overlay(self, request) -> None:
        with self._MappedArray(request, "main") as m:
            _desenhar_cv2(self._cv2, m.array, self._get_angle(), self._get_alarme())

    def read_jpeg(self) -> bytes:
        with self._stream.condition:
            self._stream.condition.wait()
            return self._stream.frame

    def set_quality(self, value: int) -> None:
        # picamera2 controla a qualidade do JpegEncoder na criação; gancho
        # mantido por contrato (RNF do próximo módulo).
        pass

    def save_clip(self, path_base: str) -> Optional[str]:
        import subprocess
        import time

        h264 = f"{path_base}.h264"
        self._circular.fileoutput = h264
        self._circular.start()
        # Deixa o buffer (últimos ~10 s) escoar para o arquivo antes de fechar.
        time.sleep(1.0)
        self._circular.stop()

        # Remuxa para .mp4 (tocável em qualquer player). ffmpeg vem no Pi OS;
        # se faltar, fica o .h264 (roda no VLC).
        mp4 = f"{path_base}.mp4"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-framerate", str(FPS), "-i", h264, "-c", "copy", mp4],
                check=True,
                capture_output=True,
            )
            import os

            os.remove(h264)
            return mp4
        except Exception as exc:  # ffmpeg ausente/erro: entrega o h264 mesmo
            print(f"[camera_stream] remux mp4 falhou ({exc}); mantendo {h264}")
            return h264


def salvar_denuncia(source: FrameSource) -> str:
    """Salva um print do frame atual (com overlay) em ``denuncias/``.

    Chamado a cada disparo do botão de alarme, para virar prova na galeria
    "Denúncias à polícia".
    """
    from pathlib import Path

    Path("denuncias").mkdir(exist_ok=True)
    nome = f"denuncias/intruso_{datetime.now():%Y%m%d_%H%M%S}.jpg"
    with open(nome, "wb") as f:
        f.write(source.read_jpeg())
    print(f"[camera_stream] denúncia salva: {nome}")
    return nome


def make_source(
    get_angle: Optional[Callable[[], float]] = None,
    get_alarme: Optional[Callable[[], bool]] = None,
) -> FrameSource:
    """Escolhe o backend disponível: CSI → USB → sintético.

    Args:
        get_angle: Callable que devolve o ângulo atual da câmera, para o
            overlay. Se ``None``, usa 90 g fixo.
        get_alarme: Callable que devolve ``True`` enquanto o alarme está
            disparado, para o overlay de intruso. Se ``None``, sempre falso.

    Returns:
        A primeira :class:`FrameSource` que inicializar sem erro. Assim o mesmo
        arquivo roda no Pi (câmera real) e na máquina de dev (sintético).
    """
    for factory in (PiCameraSource, UsbCameraSource, SyntheticSource):
        try:
            source = factory(get_angle=get_angle, get_alarme=get_alarme)
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
    """Cria a aplicação Flask que serve a página do porteiro e o stream MJPEG.

    Flask é importado localmente para o módulo poder ser importado (e testado)
    sem Flask instalado na máquina de desenvolvimento.
    """
    import time
    from pathlib import Path

    from flask import Flask, Response, jsonify, send_from_directory

    app = Flask(__name__)
    CLIPS_DIR = Path("clips")
    DENUNCIAS_DIR = Path("denuncias")

    @app.route("/")
    def index():
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Porteiro — vídeo</title></head>"
            "<body style='margin:0;background:#111;font-family:sans-serif'>"
            "<img src='/stream' style='width:100%;height:auto;display:block'>"
            "<div style='position:fixed;bottom:16px;left:0;right:0;"
            "display:flex;gap:12px;justify-content:center'>"
            "<button onclick=\"fetch('/save',{method:'POST'}).then(async r=>{"
            "if(!r.ok){alert(await r.text());return;}"
            "const j=await r.json();alert('Salvo: '+j.arquivo);})"
            ".catch(()=>alert('Falha ao salvar'))\" "
            "style='padding:12px 20px;font-size:16px;border:0;border-radius:8px;"
            "background:#c33;color:#fff;cursor:pointer'>Salvar últimos 10 s</button>"
            "<a href='/clips' style='padding:12px 20px;font-size:16px;"
            "border-radius:8px;background:#333;color:#fff;text-decoration:none'>"
            "Ver gravações</a>"
            "<a href='/denuncias' style='padding:12px 20px;font-size:16px;"
            "border-radius:8px;background:#333;color:#fff;text-decoration:none'>"
            "Denúncias</a>"
            "</div></body></html>"
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

    @app.route("/save", methods=["POST"])
    def save():
        CLIPS_DIR.mkdir(exist_ok=True)
        base = f"clips/porteiro_{datetime.now():%Y%m%d_%H%M%S}"
        out = source.save_clip(base)
        if out is None:
            return (
                "Salvar clipe só na câmera CSI do Pi (backend atual não tem buffer).",
                501,
            )
        return jsonify(arquivo=out)

    @app.route("/clips")
    def clips():
        # Lista os clipes salvos (mais novos primeiro): mp4 toca no navegador,
        # h264 fica como download.
        arquivos = sorted(
            CLIPS_DIR.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True
        ) if CLIPS_DIR.exists() else []
        itens = "".join(
            (
                f"<div style='margin:16px 0'><p>{p.name}</p>"
                + (
                    f"<video src='/clips/{p.name}' controls "
                    "style='max-width:100%;border-radius:8px'></video>"
                    if p.suffix == ".mp4"
                    else ""
                )
                + f"<p><a href='/clips/{p.name}' download style='color:#8bf'>"
                "baixar</a></p></div>"
            )
            for p in arquivos
        ) or "<p>Nenhuma gravação ainda.</p>"
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Porteiro — gravações</title></head>"
            "<body style='margin:0;padding:16px;background:#111;color:#eee;"
            "font-family:sans-serif'>"
            "<a href='/' style='color:#8bf'>← voltar ao vídeo</a>"
            "<h2>Gravações</h2>" + itens + "</body></html>"
        )

    @app.route("/clips/<path:nome>")
    def clip_file(nome):
        return send_from_directory(CLIPS_DIR, nome)

    @app.route("/denuncias")
    def denuncias():
        # Galeria dos prints salvos a cada disparo do botão de alarme.
        fotos = sorted(
            DENUNCIAS_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True
        ) if DENUNCIAS_DIR.exists() else []
        itens = "".join(
            f"<figure style='margin:0'><img src='/denuncias/{p.name}' "
            "style='width:100%;border-radius:8px'>"
            f"<figcaption style='font-size:13px;color:#aaa'>{p.name}</figcaption>"
            "</figure>"
            for p in fotos
        ) or "<p>Nenhuma denúncia registrada.</p>"
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Porteiro — denúncias à polícia</title></head>"
            "<body style='margin:0;padding:16px;background:#111;color:#eee;"
            "font-family:sans-serif'>"
            "<a href='/' style='color:#8bf'>← voltar ao vídeo</a>"
            "<h2>Denúncias à polícia</h2>"
            "<div style='display:grid;grid-template-columns:"
            "repeat(auto-fill,minmax(240px,1fr));gap:12px'>" + itens + "</div>"
            "</body></html>"
        )

    @app.route("/denuncias/<path:nome>")
    def denuncia_file(nome):
        return send_from_directory(DENUNCIAS_DIR, nome)

    return app


def main() -> None:
    """Sobe o porteiro: joystick em thread + servidor de vídeo na rede local."""
    import joystick_servo

    import alarme

    ctrl = joystick_servo.start_in_thread()
    get_angle = (lambda: ctrl.angle) if ctrl else (lambda: float(90))

    alarm = alarme.start()
    get_alarme = (lambda: alarm.ativo) if alarm else (lambda: False)

    source = make_source(get_angle, get_alarme)

    # No disparo do botão (GPIO21): sirene + banner no vídeo (via alarm.ativo)
    # + print salvo como denúncia.
    if alarm:
        alarm.on_disparo = lambda: salvar_denuncia(source)

    app = create_app(source)
    # threaded=True: o /stream mantém a conexão aberta; sem isso, / e /save
    # ficariam bloqueados enquanto alguém assiste.
    app.run(host="0.0.0.0", port=PORT, threaded=True)


if __name__ == "__main__":
    main()
