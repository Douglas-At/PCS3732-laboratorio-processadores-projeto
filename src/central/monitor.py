"""Computador central — monitoramento, latência e alarme.

Consolida os serviços da camada central descritos no diagrama de blocos
(``docs/diagramas/diagrama_blocos.png``):

* **Serviço de Vídeo / Dashboard** — conecta em ``GET /stream`` da borda e
  exibe o vídeo em tempo real; permite ajustar a qualidade
  (``GET /control?var=quality&val=X``).
* **Monitor de Latência** — mede o tempo de chegada de cada frame e sinaliza
  quando ultrapassa o limiar.
* **Serviço de Alarme/Notificação** — recebe o ``POST /alert`` da borda,
  responde ``200 OK`` (ACK), dispara a notificação e registra em log.

Nota (Semana 1): apenas esqueleto com contratos e docstrings. A interface e os
serviços entram nas Semanas 2–3.
"""

from __future__ import annotations


def start_dashboard(stream_url: str) -> None:
    """Inicia a interface de monitoramento consumindo o stream da borda.

    Args:
        stream_url: URL do endpoint ``GET /stream`` da borda.
    """
    raise NotImplementedError("Dashboard implementado nas Semanas 2-3")


def handle_alert() -> None:
    """Processa um alerta recebido em ``POST /alert``.

    Responde com ACK, dispara a notificação de emergência e registra o evento
    no log.
    """
    raise NotImplementedError("Serviço de alarme implementado na Semana 2")
