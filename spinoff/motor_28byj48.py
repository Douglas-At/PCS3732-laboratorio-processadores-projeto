#!/usr/bin/env python3
# =========================================
# MOTOR DE PASSO 28BYJ-48 (+ driver ULN2003) CONTROLADO PELO JOYSTICK
# Raspberry Pi 3 + RPi.GPIO (BCM)
#
# Spinoff do porteiro: o eixo X do joystick controla o motor por
# VELOCIDADE — empurrar p/ um lado gira num sentido (mais rapido
# quanto mais longe do centro); o outro lado inverte; centro para.
#
# A leitura do joystick (ADS7830, canal X) e REUTILIZADA de
# src/rpi/joystick_servo.py (ler_x, normaliza) — mesmo ADC do kit.
#
# ULN2003: IN1-IN4 -> os 4 GPIO de IN_PINS. Alimentar a placa em 5V
# com GND COMUM ao Raspberry. Motor no conector branco da placa.
#
# Sequencia de MEIO-PASSO (8 fases): ~4096 meio-passos = 1 volta.
#
# Uso:  sudo python3 motor_28byj48.py           (joystick controla o motor)
#       sudo python3 motor_28byj48.py --spin     (gira ida e volta, sem joystick)
#       python3 motor_28byj48.py --test          (auto-teste no PC, sem hardware)
# =========================================

import argparse
import pathlib
import sys
import time

# --- Knobs de hardware (ajuste conforme sua bancada) ---
IN_PINS = [6, 13, 19, 26]   # BCM -> ULN2003 IN1..IN4 (nao colidem com o porteiro)
STEP_DELAY = 0.002          # s entre passos no modo --spin
STEP_DELAY_MIN = 0.0015     # joystick no talo -> mais rapido (menor pausa)
STEP_DELAY_MAX = 0.02       # joystick perto do centro -> mais devagar
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


def delay_do_norm(norm):
    """Deflexao do joystick (|norm| in (0,1]) -> pausa entre passos (s).

    Mais empurrado = mais rapido = menor pausa (interpola MAX->MIN).
    """
    m = min(1.0, abs(norm))
    return STEP_DELAY_MAX + (STEP_DELAY_MIN - STEP_DELAY_MAX) * m


def laco_joystick(ler_norm, escrever, dormir=time.sleep, parar=lambda: False):
    """Laco de velocidade: o joystick define sentido e rapidez do motor.

    Tudo injetado (``ler_norm``, ``escrever``, ``dormir``, ``parar``) para
    o auto-teste rodar sem hardware.

    Args:
        ler_norm: Callable -> float em [-1,1] (0 = centro/zona morta).
        escrever: Callable(padrao) -> aplica [in1..in4] nos pinos.
        dormir: Callable(s) de pausa (injetavel no teste).
        parar: Callable -> True para encerrar o laco.

    Returns:
        Indice da fase corrente ao sair.
    """
    idx = 0
    while not parar():
        norm = ler_norm()
        if norm == 0.0:
            escrever([0, 0, 0, 0])  # solta as bobinas quando parado (nao esquenta)
            dormir(0.02)
            continue
        sentido = 1 if norm > 0 else -1
        idx = (idx + sentido) % len(SEQ)
        escrever(SEQ[idx])
        dormir(delay_do_norm(norm))
    return idx


def _init_gpio():
    """Inicializa RPi.GPIO e devolve (escrever, cleanup), ou None sem hardware."""
    try:
        import RPi.GPIO as GPIO
    except Exception as exc:  # ImportError no PC, etc.
        print(f"[motor_28byj48] GPIO indisponivel: {exc}")
        return None

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pino in IN_PINS:
        GPIO.setup(pino, GPIO.OUT, initial=GPIO.LOW)

    def escrever(padrao):
        for pino, valor in zip(IN_PINS, padrao):
            GPIO.output(pino, valor)

    def cleanup():
        escrever([0, 0, 0, 0])  # desliga as bobinas
        GPIO.cleanup()

    return escrever, cleanup


def _init_joystick():
    """Abre o ADS7830 e devolve ``ler_norm`` (-> [-1,1]), ou None sem hardware.

    Reutiliza ``ler_x`` e ``normaliza`` de src/rpi/joystick_servo.py.
    """
    try:
        import smbus
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src" / "rpi"))
        from joystick_servo import ler_x, normaliza
    except Exception as exc:  # sem smbus/I2C no PC, etc.
        print(f"[motor_28byj48] joystick indisponivel: {exc}")
        return None

    bus = smbus.SMBus(1)
    return lambda: normaliza(ler_x(bus))


def demo():
    """Auto-teste sem hardware: python3 motor_28byj48.py --test"""
    # Tabela de fases bem formada: 8 padroes de 4 bits 0/1.
    assert len(SEQ) == 8
    assert all(len(p) == 4 and all(v in (0, 1) for v in p) for p in SEQ)

    # passo() aplica exatamente n escritas; ida e volta fecham a fase.
    escritas = []
    passo(20, +1, escritas.append, delay=0)
    assert len(escritas) == 20
    assert passo(len(SEQ), +1, lambda _: None, delay=0) == 0
    assert passo(5, -1, lambda _: None, delay=0) == len(SEQ) - 5

    # Joystick: mais empurrado = pausa menor (mais rapido).
    assert delay_do_norm(1.0) == STEP_DELAY_MIN
    assert delay_do_norm(0.3) > delay_do_norm(0.9)

    # laco_joystick: empurrado num sentido, da um passo por iteracao.
    passos, conta = [], {"i": 0}
    def parar():
        conta["i"] += 1
        return conta["i"] > 3
    laco_joystick(lambda: 1.0, passos.append, dormir=lambda _: None, parar=parar)
    assert len(passos) == 3, f"esperava 3 passos, veio {len(passos)}"

    print("demo OK: fases, contagem de passos e mapeamento do joystick consistentes")


def main():
    ap = argparse.ArgumentParser(description="28BYJ-48 controlado pelo joystick")
    ap.add_argument("--test", action="store_true", help="auto-teste sem hardware")
    ap.add_argument("--spin", action="store_true", help="gira ida e volta, sem joystick")
    ap.add_argument("--voltas", type=float, default=1.0, help="voltas no modo --spin")
    args = ap.parse_args()

    if args.test:
        demo()
        return

    hw = _init_gpio()
    if hw is None:
        print("Sem GPIO. Rode com --test no PC.")
        return
    escrever, cleanup = hw

    try:
        if args.spin:
            n = int(args.voltas * PASSOS_POR_VOLTA)
            print(f"\n== 28BYJ-48: {args.voltas} volta(s) de ida e volta (Ctrl+C sai) ==")
            passo(n, +1, escrever)
            time.sleep(0.5)
            passo(n, -1, escrever)
            print(" fim.")
            return

        ler_norm = _init_joystick()
        if ler_norm is None:
            print("Sem joystick (I2C/ADS7830). Use --spin para girar sem ele.")
            return
        print("\n== 28BYJ-48 pelo joystick (empurre X; centro para; Ctrl+C sai) ==")
        laco_joystick(ler_norm, escrever)
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
