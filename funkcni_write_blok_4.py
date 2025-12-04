import mfrc522     # https://github.com/cefn/micropython-mfrc522
from machine import Pin, SPI, PWM
from time import sleep_ms
import buzzer_test # Předpokládá se existence tohoto modulu
import dip_switch_setup

STATION_ID = dip_switch_setup.station_id()


# --- Nastavení Hardwaru ---
buzzer = PWM(Pin(25))

# RFID čtečka - SPI sběrnice
sck = Pin(18, Pin.OUT)
mosi = Pin(23, Pin.OUT)
miso = Pin(19, Pin.IN)

cs = Pin(5, Pin.OUT)
rst = Pin(17, Pin.OUT)

# Vestavěná LED simulující relé zámku
rele = Pin(2, Pin.OUT)

vspi = SPI(2, baudrate=100000, polarity=0, phase=0, sck=sck, mosi=mosi, miso=miso)

rdr = mfrc522.MFRC522(spi=vspi, gpioRst=rst, gpioCs=cs)

buzzer_test.bud_zticha()

print('Prilozte kartu')

# Klíč pro autentizaci (výchozí pro Mifare Classic)
KEY = b'\xff\xff\xff\xff\xff\xff'
# Data pro zápis (musí být přesně 16 bytů)
DATA_TO_WRITE = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"


def do_write():
    raw_uid = [0, 0, 0, 0] 

    try:
        while True:
            rele.off()
            (stat, tag_type) = rdr.request(rdr.REQIDL)

            if stat == rdr.OK:

                (stat, raw_uid_temp) = rdr.anticoll()

                if stat == rdr.OK:
                    raw_uid = raw_uid_temp
                    print("--- New card detected ---")
                    print("  - uid  : 0x%02x%02x%02x%02x" % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3]))
                    print("")

                    if rdr.select_tag(raw_uid) == rdr.OK:
                        
                        # Cílový blok, který chceme zkusit (např. Block 4)
                        #block_addr =  (STATION_ID*4)
                            
                        print(f"** Trying Block {block_addr} **")
                            
                        # 1. AUTENTIZACE
                        if rdr.auth(rdr.AUTHENT1A, block_addr, KEY, raw_uid) == rdr.OK:
                            print(f"  -> Authentication success for Block {block_addr}.")

                            # 2. ZÁPIS DAT
                            stat_w = rdr.write(block_addr, DATA_TO_WRITE)
                            
                            rdr.stop_crypto1() # Zastavit šifrování ihned po zápisu
                            
                            if stat_w == rdr.OK:
                                print(f"  -> SUCCESS: Data written to Block {block_addr}.")
                            else:
                                print(f"  -> FAILED: Could not write data to Block {block_addr}.")
                        else:
                            print(f"  -> ERROR: Authentication failed for Block {block_addr}.")
                            rdr.stop_crypto1() # Zastavit šifrování
                        
                        # Krátká pauza, po které uživatel kartu odebere a znovu přiloží
                        sleep_ms(2000)
                        print("\nPrilozte kartu")
                    else:
                        print("Failed to select tag")

    except KeyboardInterrupt:
        print("Bye")
        
do_write()
