# Camada de Borda (Raspberry Pi)

Código que roda no Raspberry Pi 3B+, junto da câmera e do botão físico.

| Arquivo | Responsabilidade | Status |
|---|---|---|
| `camera_stream.py` | Servidor Flask do porteiro: `GET /` (vídeo + botão salvar), `GET /stream` (MJPEG), `POST /save` (últimos 10 s). Overlay de horário + ângulo queimado no frame. Captura plugável (`picamera2` CSI → OpenCV USB → sintético). | Porteiro ✔ |
| `joystick_servo.py` | Laço do joystick Freenove (ADS7830) → servo (RPi.GPIO PWM). `ServoController` roda em thread e publica o ângulo (`self.angle`) que o vídeo mostra. | ✔ |
| `alarme.py` | Botão de emergência via `gpiozero.Button` (debounce por `bounce_time`) → `POST /alert` para o central, com ACK e retry/backoff. | Esqueleto |

> O backend de câmera é escolhido automaticamente por `make_source()` na ordem
> CSI → USB → sintético, então o mesmo arquivo roda no Pi e na máquina de dev.

## Interface de porteiro

Ao abrir `http://<ip-do-pi>:5000/`, o vídeo já vem com **horário** e **ângulo da
câmera** queimados em cada frame. O ângulo é o do servo, panorado em tempo real
pelo joystick (`joystick_servo.py`, iniciado junto do servidor). O botão
**"Salvar últimos 10 s"** dispara `POST /save`.

- **Salvar clipe é exclusivo do Pi com câmera CSI**: o `picamera2` mantém um
  buffer circular H264 dos últimos ~10 s (remuxado para `.mp4` via `ffmpeg`,
  gravado em `clips/`). Nos backends USB/sintético, `POST /save` responde `501`.
- O servo precisa de GPIO, então o porteiro roda com `sudo`. Sem hardware de
  joystick/servo, o servidor sobe mesmo assim e o ângulo fica fixo em 90 g.

## Rodar o servidor de vídeo (Módulo 1)

**No Raspberry Pi:**

```bash
sudo apt install -y python3-picamera2 python3-opencv ffmpeg
pip install flask
sudo python camera_stream.py   # sudo pela GPIO do servo; escuta em 0.0.0.0:5000
hostname -I                    # descobre o IP do Pi
```

De **outro computador** na mesma Wi-Fi, abra no navegador `http://<ip-do-pi>:5000/`
— a página exibe o vídeo ao vivo (RF1) com horário + ângulo, e o botão de salvar
os últimos 10 s. Nenhum programa "central" é necessário só para assistir.

**Na máquina de desenvolvimento (sem câmera):** `pip install flask pillow` e
`python camera_stream.py` cai no backend sintético (um relógio que anda), útil para
validar o streaming antes de ir ao Pi. Se a porta 5000 estiver ocupada, ajuste
`PORT` no topo do arquivo.
