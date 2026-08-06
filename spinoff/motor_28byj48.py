#!/usr/bin/env python3
# =========================================
# TESTE DE BANCADA — MOTOR DE PASSO 28BYJ-48 (+ driver ULN2003)
# Raspberry Pi 3 + RPi.GPIO (BCM)
#
# Spinoff isolado do porteiro: so para ver o motor girar e confirmar
# que a fiacao/driver funcionam. Nada de integracao com o resto.
#
# ULN2003: IN1-IN4 -> os 4 GPIO de IN_PINS. Alimentar a placa em 5V
# com GND COMUM ao Raspberry. Motor no conector branco da placa.
#
# Sequencia de MEIO-PASSO (8 fases): mais suave e com mais torque
# que passo cheio. ~4096 meio-passos = 1 volta (reducao interna ~1:64).
#
# Uso:  sudo python3 motor_28byj48.py           (gira no Pi real)
#       python3 motor_28byj48.py --test          (auto-teste no PC, sem hardware)
#       sudo python3 motor_28byj48.py --voltas 3 (gira 3 voltas de ida e volta)
# =========================================

import argparse
import time

# --- Knobs de hardware (ajuste conforme sua bancada) ---
IN_PINS = [6, 13, 19, 26]   # BCM -> ULN2003 IN1..IN4 (nao colidem com o porteiro)
STEP_DELAY = 0.002          # s entre passos; rapido demais o motor trava/chia
PASSOS_POR_VOLTA = 4096     # meio-passo, com a reducao interna ~1:64

# Sequencia de meio-passo (8 fases). Cada linha e o estado de IN1..IN4.
SEQ = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1],
]


def passo(n, sentido, escrever, delay=STEP_DELAY):
    """Avanca ``n`` meio-passos, aplicando cada padrao da sequencia.

    A escrita nos pinos e injetada (``escrever``) para o auto-teste rodar
    sem GPIO — mesma filosofia do ServoController do joystick_servo.py.

    Args:
        n: Numero de meio-passos.
        sentido: +1 (horario) ou -1 (anti-horario).
        escrever: Callable(padrao) -> aplica a lista [in1..in4] nos pinos.
        delay: Pausa (s) entre passos.

    Returns:
        Indice da proxima fase (0-7), util para encadear chamadas/testes.
    """
    idx = 0
    for _ in range(n):
        idx = (idx + sentido) % len(SEQ)
        escrever(SEQ[idx])
        time.sleep(delay)
    return idx


def _init_gpio():
    """Inicializa RPi.GPIO e devolve (escrever, cleanup), ou None sem hardware."""
    try:
        import RPi.GPIO as GPIO
    except Exception as exc:  # ImportError no PC, etc.
        print(f"[motor_28byj48] hardware indisponivel: {exc}")
        return None

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pino in IN_PINS:
        GPIO.setup(pino, GPIO.OUT, initial=GPIO.LOW)

    def escrever(padrao):
        for pino, valor in zip(IN_PINS, padrao):
            GPIO.output(pino, valor)

    def cleanup():
        escrever([0, 0, 0, 0])  # desliga as bobinas (nao esquenta parado)
        GPIO.cleanup()

    return escrever, cleanup


def demo():
    """Auto-teste sem hardware: python3 motor_28byj48.py --test"""
    # Tabela de fases bem formada: 8 padroes de 4 bits 0/1.
    assert len(SEQ) == 8
    assert all(len(p) == 4 and all(v in (0, 1) for v in p) for p in SEQ)

    # passo() aplica exatamente n escritas.
    escritas = []
    passo(20, +1, escritas.append, delay=0)
    assert len(escritas) == 20

    # Ida e volta pelo mesmo numero de passos volta a fase inicial.
    fim = passo(len(SEQ), +1, lambda _: None, delay=0)
    assert fim == 0, f"apos uma volta de fases o indice deveria zerar, veio {fim}"
    assert passo(5, -1, lambda _: None, delay=0) == len(SEQ) - 5

    print("demo OK: sequencia de 8 fases e contagem de passos consistentes")


def main():
    ap = argparse.ArgumentParser(description="Teste do motor de passo 28BYJ-48")
    ap.add_argument("--test", action="store_true", help="auto-teste sem hardware")
    ap.add_argument("--voltas", type=float, default=1.0, help="voltas de ida e volta")
    args = ap.parse_args()

    if args.test:
        demo()
        return

    hw = _init_gpio()
    if hw is None:
        print("Sem GPIO. Rode com --test no PC.")
        return
    escrever, cleanup = hw

    n = int(args.voltas * PASSOS_POR_VOLTA)
    print(f"\n== 28BYJ-48: {args.voltas} volta(s) de ida e volta (Ctrl+C sai) ==")
    try:
        print(" girando horario...")
        passo(n, +1, escrever)
        time.sleep(0.5)
        print(" girando anti-horario...")
        passo(n, -1, escrever)
        print(" fim.")
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
