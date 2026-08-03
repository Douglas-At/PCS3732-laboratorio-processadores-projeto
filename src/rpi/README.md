# Camada de Borda (Raspberry Pi)

Código que roda no Raspberry Pi 3B+, junto da câmera e do botão físico.

| Arquivo | Responsabilidade |
|---|---|
| `camera_stream.py` | Servidor Flask com `GET /stream` (MJPEG) e `GET /control?var=quality&val=X`. Captura plugável: `picamera2` (módulo CSI) ou OpenCV (câmera USB). |
| `alarme.py` | Botão de emergência via `gpiozero.Button` (debounce por `bounce_time`) → `POST /alert` para o central, com ACK e retry/backoff. |

> Semana 1: esqueletos com contratos e docstrings. Implementação funcional nas Semanas 2–3.
> O backend de câmera depende da disponibilidade do módulo CSI (ver relatório).
