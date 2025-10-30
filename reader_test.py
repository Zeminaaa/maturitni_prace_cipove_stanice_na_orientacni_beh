import mfrc522     # https://github.com/cefn/micropython-mfrc522
from machine import Pin, SPI, PWM
from time import sleep_ms
import buzzer_test

buzzer = PWM(Pin(25))

#RFID ctecka - SPI sbernice
sck = Pin(18, Pin.OUT)
mosi = Pin(23, Pin.OUT)
miso = Pin(19, Pin.IN)

cs = Pin(5, Pin.OUT)
rst = Pin(17, Pin.OUT)

# vestavena LED simulujici rele zamku
rele = Pin(2, Pin.OUT)

vspi = SPI(2, baudrate=100000, polarity=0, phase=0, sck=sck, mosi=mosi, miso=miso)

#vspi = SPI(2)
rdr = mfrc522.MFRC522(spi=vspi, gpioRst=rst, gpioCs=cs)

print('Prilozte kartu')

while True:
    rele.off()
    (stat, tag_type) = rdr.request(rdr.REQIDL)
    if stat == rdr.OK:
        (stat, raw_uid) = rdr.anticoll()
        if stat == rdr.OK:
            print('Detekovano!')
            buzzer_test.ano_sound()
            print('type: 0x%02X' % tag_type)
            print('uid: %02X-%02X-%02X-%02X-%02X' % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3], raw_uid[4]))
            print('')
            rele.on()
            sleep_ms(1000)
            print('Prilozte kartu')
