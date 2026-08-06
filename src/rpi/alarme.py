"""Botão de emergência da camada de borda (Raspberry Pi).

Ao pressionar o botão físico, a borda notifica o computador central para que
este dispare a notificação de emergência (ver
``docs/diagramas/sequencia_alarme.d2``):

1. Interrupção de GPIO ao pressionar o botão.
2. Debounce (~50 ms) para evitar leituras falsas do contato mecânico.
3. ``POST /alert`` para o Serviço de Alarme central, aguardando ``200 OK`` (ACK).
4. Em falha de rede, retransmite com *retry* e *backoff*.

Baseia-se no padrão de botão por evento do kit Freenove
(``Code/Python_GPIOZero_Code/6_1_Doorbell/Doorbell.py``), usando
``gpiozero.Button`` com callback ``when_pressed``. O debounce é calibrado pelo
parâmetro ``bounce_time`` do ``Button`` — ajustável ao contato usado.

Nota (Semana 1): apenas esqueleto com contratos e docstrings. O envio HTTP com
ACK/retry entra na Semana 2.
"""

from __future__ import annotations


DEBOUNCE_S = 0.05  # ~50 ms


def on_button_pressed() -> None:
    """Callback de borda de subida do botão de emergência.

    Deve enviar ``POST /alert`` ao Serviço de Alarme central e, em falha de
    rede, retransmitir com *retry*/*backoff*.
    """

    raise NotImplementedError("Envio do alerta implementado na Semana 2")


def build_button(pin: int = 21):
    """Cria o ``gpiozero.Button`` do alarme com debounce configurado.

    Args:
        pin: Pino BCM do botão (padrão 21, como no exemplo Doorbell do kit).

    Returns:
        Instância de ``gpiozero.Button`` com ``on_button_pressed`` conectado.
    """
    from gpiozero import Button

    button = Button(pin, bounce_time=DEBOUNCE_S)
    button.when_pressed = on_button_pressed
    return button
