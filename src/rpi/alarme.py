"""Botão de emergência da camada de borda (Raspberry Pi).

Ao pressionar o botão físico (GPIO21), a borda dispara um alarme local:

1. **Sirene** no buzzer passivo (GPIO17), alternando duas notas (som de
   polícia), via ``gpiozero.TonalBuzzer``.
2. **Aviso visual** no vídeo do porteiro — o overlay pinta "INTRUSO
   DETECTADO / CHAMANDO A POLICIA" enquanto ``AlarmController.ativo`` é
   verdadeiro (lido por ``camera_stream``).
3. **Denúncia** — um print da câmera é salvo (callback ``on_disparo``), para a
   galeria "Denúncias à polícia".

Baseia-se no padrão de botão por evento do kit Freenove
(``Doorbell.py``): ``gpiozero.Button`` com ``when_pressed`` e debounce por
``bounce_time``. O buzzer passivo precisa de tom (PWM), por isso ``TonalBuzzer``
e não um ``Buzzer`` liga/desliga.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

BUTTON_PIN = 21
BUZZER_PIN = 17          # ponytail: pino do buzzer passivo; ajustar ao circuito
# ponytail: valor inicial; recalibrar contra o contato mecânico real do botão.
DEBOUNCE_S = 0.05        # ~50 ms
DURACAO_S = 10.0         # quanto tempo o alarme fica ativo por acionamento
SIRENE_HZ = (440.0, 880.0)  # duas notas alternadas = sirene
SIRENE_PERIODO = 0.5     # troca de nota a cada 0,5 s


class AlarmController:
    """Alarme disparado pelo botão: sirene + flag visual + denúncia.

    A emissão de som (``nota``) é injetada para o laço rodar igual com
    hardware (buzzer) ou sem (teste no PC).

    Args:
        nota: Callable(freq | None) — toca a frequência (Hz) ou silencia (None).
        duracao: Segundos que o alarme fica ativo por acionamento.
        periodo: Segundos entre a troca das notas da sirene.
    """

    def __init__(
        self,
        nota: Optional[Callable[[Optional[float]], None]] = None,
        duracao: float = DURACAO_S,
        periodo: float = SIRENE_PERIODO,
    ) -> None:
        self._nota = nota or (lambda freq: None)
        self.duracao = duracao
        self.periodo = periodo
        self.ativo = False
        # Callback opcional chamado no disparo (ex.: salvar print de denúncia).
        self.on_disparo: Callable[[], None] = lambda: None

    def disparar(self) -> None:
        """Aciona o alarme (ignora se já estiver ativo). Não bloqueia."""
        if self.ativo:
            return
        self.ativo = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            self.on_disparo()  # print da denúncia no instante do disparo
        except Exception as exc:  # não deixa o alarme cair se o print falhar
            print(f"[alarme] on_disparo falhou: {exc}")
        fim = time.time() + self.duracao
        i = 0
        while self.ativo and time.time() < fim:
            self._nota(SIRENE_HZ[i % 2])
            i += 1
            time.sleep(self.periodo)
        self._nota(None)  # silencia
        self.ativo = False


def start(button_pin: int = BUTTON_PIN, buzzer_pin: int = BUZZER_PIN):
    """Inicializa botão + buzzer e devolve o ``AlarmController`` armado.

    Espelha ``joystick_servo.start_in_thread``: sem hardware (máquina de dev),
    retorna ``None`` e o chamador segue sem alarme.

    Returns:
        AlarmController pronto, ou ``None`` se gpiozero/hardware faltarem.
    """
    try:
        from gpiozero import Button, TonalBuzzer
        from gpiozero.tones import Tone
    except Exception as exc:  # ImportError no PC, etc.
        print(f"[alarme] hardware indisponivel: {exc}")
        return None

    buzzer = TonalBuzzer(buzzer_pin)

    def nota(freq: Optional[float]) -> None:
        if freq is None:
            buzzer.stop()
        else:
            buzzer.play(Tone(freq))

    ctrl = AlarmController(nota=nota)
    button = Button(button_pin, bounce_time=DEBOUNCE_S)
    button.when_pressed = ctrl.disparar
    # Mantém refs vivas (gpiozero solta o pino se o objeto for coletado).
    ctrl._refs = (button, buzzer)
    print(f"[alarme] armado: botao GPIO{button_pin}, buzzer GPIO{buzzer_pin}")
    return ctrl


def demo():
    """Auto-teste sem hardware: python3 alarme.py --test"""
    tocadas = []
    ctrl = AlarmController(nota=tocadas.append, duracao=0.3, periodo=0.05)
    ctrl.disparar()
    assert ctrl.ativo, "deve ficar ativo logo após disparar"
    time.sleep(0.5)  # deixa o ciclo terminar
    assert not ctrl.ativo, "deve desligar sozinho após a duração"
    assert SIRENE_HZ[0] in tocadas and SIRENE_HZ[1] in tocadas, "sirene alterna 2 notas"
    assert tocadas[-1] is None, "deve silenciar no fim"
    print("demo OK: sirene alterna 2 notas, desliga sozinha e silencia")


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Alarme por botão (sirene + denúncia)")
    ap.add_argument("--test", action="store_true", help="auto-teste sem hardware")
    args = ap.parse_args()

    if args.test:
        demo()
        return

    ctrl = start()
    if ctrl is None:
        print("Sem hardware de GPIO. Rode com --test no PC.")
        return
    print(f"\n== Alarme armado (Ctrl+C para sair). Pressione o botao GPIO{BUTTON_PIN} ==")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nInterrompido.")


if __name__ == "__main__":
    main()
