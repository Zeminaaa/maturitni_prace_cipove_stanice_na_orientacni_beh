import mfrc522     # https://github.com/cefn/micropython-mfrc522
from machine import Pin, SPI, PWM
from time import sleep_ms
import buzzer_test

buzzer = PWM(Pin(25))

# RFID ctecka - SPI sbernice
sck = Pin(18, Pin.OUT)
mosi = Pin(23, Pin.OUT)
miso = Pin(19, Pin.IN)

cs = Pin(5, Pin.OUT)
rst = Pin(17, Pin.OUT)

# vestavena LED simulujici rele zamku
rele = Pin(2, Pin.OUT)

# BAUD RATE ZNIZEN NA 50000 PRO VETSI STABILITU
# Původní kód ve vašem reader_test.py měl 100000, ale ponecháme 50000 pro stabilitu
vspi = SPI(2, baudrate=50000, polarity=0, phase=0, sck=sck, mosi=mosi, miso=miso)

rdr = mfrc522.MFRC522(spi=vspi, gpioRst=rst, gpioCs=cs)

buzzer_test.bud_zticha()

print('Prilozte kartu')

# --- KONSTANTY PRO CTENI BLOKU ---
TARGET_BLOCKS = [4,8,12,16,20,24,28,32,36,40,44,48,52,56,60]                                
KEY = b'\xff\xff\xff\xff\xff\xff'               

while True:
    rele.off()
    (stat, tag_type) = rdr.request(rdr.REQIDL)
    
    if stat == rdr.OK:
        (stat, raw_uid) = rdr.anticoll()
        
        if stat == rdr.OK:
            print('Detekovano!')
            buzzer_test.ano_sound()
            
            print('type: 0x%02X' % tag_type)
            # Upraveno zobrazení UID, protože Mifare Classic má 4 byty.
            print('uid: %02X-%02X-%02X-%02X' % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3]))
            
            # --- PRIDANE CTENI BLOKU 4 ---
            if rdr.select_tag(raw_uid) == rdr.OK:
                
                for target_block in TARGET_BLOCKS:
                    # 2. Autentizace na blok
                    if rdr.auth(rdr.AUTHENT1A, target_block, KEY, raw_uid) == rdr.OK:
                        
                        print(f'Autentizace pro Blok {target_block} OK.')
                        
                        try:
                            # !!! KLÍČOVÁ ZMĚNA: RDR.READ() VRACÍ POUZE JEDNU HODNOTU (DATA NEBO NONE) !!!
                            data = rdr.read(target_block) 
                            rdr.stop_crypto1() # Vždy zastavit šifrování
                            
                            if data is not None:
                                # Čtení bylo úspěšné
                                print(f'** BLOK {target_block} USPESNE PRECTEN **')
                                # Data vypisujeme v HEX, aby byla vidět i binární data z vašeho zápisu
                                print('Raw Data (HEX):', ''.join(['%02X' % b for b in data]))
                            else:
                                # Čtení selhalo (vráceno None)
                                print(f'CHYBA CTENI BLOKU {target_block}: Selhalo čtení dat po autentizaci.')

                        except Exception as e:
                            # Zachycení neočekávané chyby (např. chyba komunikace)
                            print(f'KRITICKÁ CHYBA KOMUNIKACE: Výjimka při čtení ({type(e).__name__}).')
                            rdr.stop_crypto1()
                    else:
                        print(f'CHYBA CTENI BLOKU {target_block}: Selhala Autentizace.')
                        rdr.stop_crypto1()
                else:
                     print('CHYBA: Selhalo Select tagu.')

            # --- Závěr ---
            print('')
            rele.on()
            sleep_ms(1000)
            print('Prilozte kartu')
