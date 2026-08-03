# Porteiro Eletrônico Inteligente

Sistema de segurança tipo porteiro eletrônico: uma câmera controlada por
**Raspberry Pi 3B+** transmite vídeo em tempo real (MJPEG via Wi-Fi) para um
**computador central** que exibe uma interface de monitoramento. Um **botão
físico** aciona uma notificação de emergência.

Projeto da disciplina **PCS3732 — Laboratório de Processadores**.

## Estrutura do repositório

```
.
├── docs/
│   ├── relatorio.md          # relatório do projeto
│   ├── diagramas/            # fontes editáveis dos diagramas (D2)
│   └── figuras/              # figuras renderizadas
├── src/
│   ├── rpi/                  # camada de borda (Raspberry Pi): câmera + botão
│   └── central/             # computador central: monitoramento, latência, alarme
├── tests/                    # matriz de rastreabilidade e testes
├── LICENSE                   # GNU GPLv3
└── README.md
```

## Arquitetura (resumo)

Três camadas de baixo acoplamento: **Borda** (RPi + câmera + botão) →
**Rede Wi-Fi** → **Computador Central**. Endpoints principais do firmware:

- `GET /stream` — vídeo MJPEG (`multipart/x-mixed-replace`).
- `GET /control?var=quality&val=X` — ajuste de qualidade.
- `POST /alert` — evento do botão de emergência (com ACK e retry).

Detalhes em [`docs/relatorio.md`](docs/relatorio.md).

## Como rodar

> **Status (Semana 1):** o repositório contém a estrutura e a documentação
> inicial. O código em `src/` são esqueletos com contratos e docstrings; a
> implementação funcional entra nas Semanas 2–3.

Pré-requisitos previstos (Raspberry Pi OS):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install flask gpiozero requests picamera2   # ou opencv-python para câmera USB
```

Execução (a ser habilitada nas próximas entregas):

```bash
# Na borda (Raspberry Pi):
python src/rpi/camera_stream.py     # servidor de vídeo (GET /stream, GET /control)
python src/rpi/alarme.py            # botão de emergência (POST /alert)

# No computador central:
python src/central/monitor.py       # dashboard, latência e alarme
```

## Licença

Distribuído sob a licença [GNU GPLv3](LICENSE).
