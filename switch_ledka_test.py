import machine
import time

switch_ledka = machine.Pin(16, machine.Pin.OUT)

while True:
    switch_ledka.value(1)
    time.sleep(1)
    switch_ledka.value(0)
    time.sleep(1)