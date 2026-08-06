"""Checagem executável do alarme por botão (sem GPIO/buzzer).

    python tests/test_alarme.py

Prova o ciclo do AlarmController: dispara → fica ativo → sirene alterna duas
notas → desliga sozinho e silencia → chama o callback de denúncia.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "rpi"))

from alarme import SIRENE_HZ, AlarmController, demo  # noqa: E402


def test_demo_passa():
    demo()


def test_disparo_chama_denuncia_e_toca_sirene():
    tocadas = []
    chamou = []
    ctrl = AlarmController(nota=tocadas.append, duracao=0.3, periodo=0.05)
    ctrl.on_disparo = lambda: chamou.append(True)
    ctrl.disparar()
    assert ctrl.ativo
    time.sleep(0.5)
    assert not ctrl.ativo, "deve desligar sozinho após a duração"
    assert chamou == [True], "callback de denúncia deve rodar 1x no disparo"
    assert SIRENE_HZ[0] in tocadas and SIRENE_HZ[1] in tocadas
    assert tocadas[-1] is None, "silencia no fim"


def test_reentrancia_ignora_segundo_disparo():
    tocadas = []
    ctrl = AlarmController(nota=tocadas.append, duracao=0.3, periodo=0.05)
    ctrl.disparar()
    ctrl.disparar()  # já ativo: deve ser ignorado, sem segundo ciclo
    time.sleep(0.5)
    assert not ctrl.ativo


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("todos os testes passaram")
