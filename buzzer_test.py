import machine
import time

# Define the frequencies of several musical notes in Hz

prvni = 698
druha = 1397
treti = 2093

ctvrta = 100
pata = 60
sesta = 40

# Create a PWM object representing pin 14 and assign it to the buzzer variable
buzzer = machine.PWM(machine.Pin(17))

# Define a tone function that takes as input a Pin object representing the buzzer, a frequency in Hz, and a duration in milliseconds
def tone(pin, frequency, duration):
    pin.freq(frequency) # Set the frequency
    pin.duty(512) # Set the duty cycle
    time.sleep_ms(duration) # Pause for the duration in milliseconds
    pin.duty(0) # Set the duty cycle to 0 to stop the tone

# Play a sequence of notes with different frequency inputs and durations
def ano_sound():
    tone(buzzer, prvni, 200)
    tone(buzzer, druha, 250)
    tone(buzzer, treti, 500)

def ne_sound():
    tone(buzzer, ctvrta, 200)
    time.sleep_ms(100)
    tone(buzzer, pata, 250)
    time.sleep_ms(100)
    tone(buzzer, sesta, 500)


ne_sound()
time.sleep(1)
ano_sound()





