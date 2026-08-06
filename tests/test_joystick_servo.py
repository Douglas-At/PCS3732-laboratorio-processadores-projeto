"""Checagem executável do controle de servo pelo joystick.

Roda sem hardware (GPIO/I2C) e sem RPi.GPIO:

    python tests/test_joystick_servo.py

Prova que o ServoController integra o joystick e converge o ângulo dentro da
faixa útil (20–160 g), respeitando zona morta e o recentrar pelo clique.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "rpi"))

from joystick_servo import ANG_MAX, ANG_MIN, ServoController, demo  # noqa: E402


def test_demo_passa():
    demo()  # faixa 20-160 g, zona morta e travas (funções puras)


def test_angulo_converge_para_max_no_talo():
    c = ServoController(read_x=lambda: 255)  # joystick no talo (+)
    for _ in range(2000):
        c.step()
    assert c.angle == ANG_MAX


def test_angulo_converge_para_min_no_talo():
    c = ServoController(read_x=lambda: 0)  # joystick no talo (-)
    for _ in range(2000):
        c.step()
    assert c.angle == ANG_MIN


def test_clique_recentra_em_90():
    c = ServoController(read_x=lambda: 255, read_sw=lambda: 0)  # SW pressionado
    for _ in range(50):
        c.step()
    assert c.angle == 90


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("todos os testes passaram")
