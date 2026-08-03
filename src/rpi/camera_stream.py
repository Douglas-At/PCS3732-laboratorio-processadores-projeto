"""Servidor de vídeo da camada de borda (Raspberry Pi).

Expõe a câmera como um stream MJPEG via HTTP, no padrão descrito na
arquitetura (ver ``docs/diagramas/sequencia_streaming.d2``):

* ``GET /stream`` — resposta ``multipart/x-mixed-replace``; cada frame é um
  JPEG independente, com latência próxima a um período de frame.
* ``GET /control?var=quality&val=X`` — ajusta parâmetros de captura
  (qualidade/resolução) em tempo de execução, sem novo firmware.

A captura fica isolada atrás da interface :class:`FrameSource` para permitir
trocar o backend sem redesenhar o servidor:

* ``PiCameraSource`` — módulo de câmera CSI via ``picamera2`` (backend primário).
* ``UsbCameraSource`` — webcam USB via OpenCV/V4L2 (fallback).

O backend definitivo depende da disponibilidade do módulo CSI (pendência de
hardware registrada no relatório).

Nota (Semana 1): este arquivo é apenas o esqueleto com contratos e docstrings.
A implementação funcional entra na Semana 2.
"""

from __future__ import annotations

from typing import Protocol


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
            value: Nível de qualidade solicitado via ``GET /control``.
        """
        ...


# ponytail: backends e servidor Flask entram na Semana 2 (dependem do hardware
# de câmera). Aqui ficam só os contratos para a arquitetura ficar visível.
