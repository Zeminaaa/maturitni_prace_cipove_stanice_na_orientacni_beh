import machine
import time

# Define the frequencies of several musical notes in Hz

#prvni = 698
#druha = 1397
#treti = 2093

ctvrta = 100
pata = 60
sesta = 40

prvni = 1047  # C6
druha = 1047  # C6  
treti = 1047  # C6 - všechny stejné



# Create a PWM object representing pin 14 and assign it to the buzzer variable
buzzer = machine.PWM(machine.Pin(25))
buzzer.duty(0)

# Define a tone function that takes as input a Pin object representing the buzzer, a frequency in Hz, and a duration in milliseconds
def tone(pin, frequency, duration):
    pin.freq(frequency) # Set the frequency
    pin.duty(512) # Set the duty cycle
    time.sleep_ms(duration) # Pause for the duration in milliseconds
    pin.duty(0) # Set the duty cycle to 0 to stop the tone


def ano_sound_old():
    tone(buzzer, prvni, 200)
    tone(buzzer, druha, 250)
    tone(buzzer, treti, 500)

def ne_sound_old():
    tone(buzzer, ctvrta, 200)
    time.sleep_ms(100)
    tone(buzzer, pata, 250)
    time.sleep_ms(100)
    tone(buzzer, sesta, 500)
    
def bud_zticha():
    tone(buzzer, prvni, 0)
    time.sleep_ms(1)
    

G5 = 784
C6 = 1047 
E6 = 1319
G6 = 1568

def ano_sound():
    tone(buzzer, G5, 120)
    time.sleep_ms(40)
    tone(buzzer, C6, 120)
    time.sleep_ms(40)
    tone(buzzer, E6, 180)
    time.sleep_ms(60)
    tone(buzzer, G6, 220)
    
G3 = 196
C3 = 131
D3 = 147
F3 = 175

def ne_sound():
    tone(buzzer, G3, 180)
    time.sleep_ms(60)
    tone(buzzer, C3, 160)
    time.sleep_ms(60)        
    tone(buzzer, D3, 140)
    time.sleep_ms(40)
    tone(buzzer, F3, 300)

#ne_sound()
#time.sleep(1)
#ano_sound()
bud_zticha()
