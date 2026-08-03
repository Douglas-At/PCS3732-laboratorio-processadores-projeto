# Computador Central

Aplicação que roda no computador central: recebe o vídeo, monitora latência e
trata o alarme.

| Arquivo | Responsabilidade |
|---|---|
| `monitor.py` | Dashboard/Serviço de Vídeo (consome `GET /stream`), Monitor de Latência e Serviço de Alarme (recebe `POST /alert`, responde ACK, notifica e registra em log). |

> Semana 1: esqueleto com contratos e docstrings. Interface e serviços nas Semanas 2–3.
