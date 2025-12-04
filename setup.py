import machine
import time

G5 = 784
C6 = 1047 
E6 = 1319
G6 = 1568
G3 = 196
C3 = 131
D3 = 147
F3 = 175

# Create a PWM object representing pin 14 and assign it to the buzzer variable
buzzer = machine.PWM(machine.Pin(25))
buzzer.duty(0)

# Define a tone function that takes as input a Pin object representing the buzzer, a frequency in Hz, and a duration in milliseconds
def tone(pin, frequency, duration):
    pin.freq(frequency) # Set the frequency
    pin.duty(512) # Set the duty cycle
    time.sleep_ms(duration) # Pause for the duration in milliseconds
    pin.duty(0) # Set the duty cycle to 0 to stop the tone

def bud_zticha():
    tone(buzzer, C3, 0)
    time.sleep_ms(1)
    
def ano_sound():
    tone(buzzer, G5, 120)
    time.sleep_ms(40)
    tone(buzzer, C6, 120)
    time.sleep_ms(40)
    tone(buzzer, E6, 180)
    time.sleep_ms(60)
    tone(buzzer, G6, 220)

def ne_sound():
    tone(buzzer, G3, 180)
    time.sleep_ms(60)
    tone(buzzer, C3, 160)
    time.sleep_ms(60)        
    tone(buzzer, D3, 140)
    time.sleep_ms(40)
    tone(buzzer, F3, 300)

bud_zticha()



def station_id():
    bit1 = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)
    bit2 = machine.Pin(12, machine.Pin.IN, machine.Pin.PULL_UP)
    bit3 = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
    bit4 = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)

    list_of_bits=[bit1,bit2,bit3,bit4]

    binary_list=[]
    for i in range(4):
        binary_list.append("*")
    index=0  
    for bit in binary_list:
        binary_list[index]=list_of_bits[index].value()
        index+=1
        
    binary_string = "".join(map(str, binary_list))
    decimal_num = int(binary_string, 2)
    return(decimal_num)

