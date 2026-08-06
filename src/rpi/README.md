# Camada de Borda (Raspberry Pi)

Código que roda no Raspberry Pi 3B+, junto da câmera e do botão físico.

| Arquivo | Responsabilidade | Status |
|---|---|---|
| `camera_stream.py` | Servidor Flask com `GET /` (visualização), `GET /stream` (MJPEG). Captura plugável (`picamera2` CSI → OpenCV USB → sintético). `GET /control` (qualidade) vem no próximo módulo. | Módulo 1 ✔ |
| `alarme.py` | Botão de emergência via `gpiozero.Button` (debounce por `bounce_time`) → `POST /alert` para o central, com ACK e retry/backoff. | Esqueleto |

> O backend de câmera é escolhido automaticamente por `make_source()` na ordem
> CSI → USB → sintético, então o mesmo arquivo roda no Pi e na máquina de dev.

## Rodar o servidor de vídeo (Módulo 1)

**No Raspberry Pi:**

```bash
pip install flask            # + backend da câmera:
pip install picamera2        #   módulo CSI (já vem no Raspberry Pi OS), OU
pip install opencv-python    #   câmera USB
python camera_stream.py      # escuta em 0.0.0.0:5000
hostname -I                  # descobre o IP do Pi
```

De **outro computador** na mesma Wi-Fi, abra no navegador `http://<ip-do-pi>:5000/`
— a página exibe o vídeo ao vivo (RF1). Nenhum programa "central" é necessário só
para assistir.

**Na máquina de desenvolvimento (sem câmera):** `pip install flask pillow` e
`python camera_stream.py` cai no backend sintético (um relógio que anda), útil para
validar o streaming antes de ir ao Pi. Se a porta 5000 estiver ocupada, ajuste
`PORT` no topo do arquivo.
