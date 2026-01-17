import mfrc522      # https://github.com/cefn/micropython-mfrc522
from machine import Pin, SPI, PWM
from time import sleep_ms
import setup

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

setup.bud_zticha()

def reset_sensor(pin_number):
    """Provede tvrdý reset RC522 modulu."""
    print("Resetuji RC522...")
    rst = Pin(pin_number, Pin.OUT)
    
    rst.value(0)       # Vypnutí (Active Low)
    sleep_ms(50)  # Krátká pauza pro jistotu
    rst.value(1)       # Zapnutí
    sleep_ms(50)  # Čas na nastartování čtečky
    
def bytes_to_ints(data):
    result = []
    # Loop through the list with a step of 2 (indices 0, 2, 4...)
    for i in range(0, len(data), 2):
        # 1. Combine the two hex strings (High byte + Low byte)
        hex_pair = data[i] + data[i+1] # Becomes "1984"
        
        # 2. Convert from Hex (base 16) to Integer (base 10)
        decimal_value = int(hex_pair, 16) # Becomes 6532
        
        # 3. Append as string (as requested)
        result.append(str(decimal_value))
        
    return result


def read(TARGET_BLOCK,KEY):
    while True:
        rele.off()
        (stat, tag_type) = rdr.request(rdr.REQIDL)
        
        if stat == rdr.OK:
            (stat, raw_uid) = rdr.anticoll()
            
            if stat == rdr.OK:
                print('Detekovano!')
                #setup.ano_sound()
                
                print('type: 0x%02X' % tag_type)
                # Upraveno zobrazení UID, protože Mifare Classic má 4 byty.
                uid=('%02X-%02X-%02X-%02X' % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3]))
                
                # --- PRIDANE CTENI BLOKU ---
                if rdr.select_tag(raw_uid) == rdr.OK:
                    
                    # 2. Autentizace na bloku
                    if rdr.auth(rdr.AUTHENT1A, TARGET_BLOCK, KEY, raw_uid) == rdr.OK:
                        
                        print(f'Autentizace pro Blok {TARGET_BLOCK} OK.')
                        
                        try:
                            # !!! KLÍČOVÁ ZMĚNA: RDR.READ() VRACÍ POUZE JEDNU HODNOTU (DATA NEBO NONE) !!!
                            data = rdr.read(TARGET_BLOCK) 
                            rdr.stop_crypto1() # Vždy zastavit šifrování
                            
                            if data is not None:
                                # Čtení bylo úspěšné
                                print(f'** BLOK {TARGET_BLOCK} USPESNE PRECTEN **')
                                # Data vypisujeme v HEX, aby byla vidět i binární data z vašeho zápisu
                                return(['%02X' % b for b in data],uid)
                                
                            else:
                                # Čtení selhalo (vráceno None)
                                setup.ne_sound()
                                print(f'CHYBA CTENI BLOKU {TARGET_BLOCK}: Selhalo čtení dat po autentizaci.')

                        except Exception as e:
                            # Zachycení neočekávané chyby (např. chyba komunikace)
                            setup.ne_sound()
                            print(f'KRITICKÁ CHYBA KOMUNIKACE: Výjimka při čtení ({type(e).__name__}).')
                            rdr.stop_crypto1()
                    else:
                        setup.ne_sound()
                        print(f'CHYBA CTENI BLOKU {TARGET_BLOCK}: Selhala Autentizace.')
                        rdr.stop_crypto1()
                else:
                    setup.ne_sound()
                    print('CHYBA: Selhalo Select tagu.')

                # --- Závěr ---
                print('')
                rele.on()
                sleep_ms(1000)
                print('Prilozte kartu')
                
                
reset_sensor(rst)
spi = SPI(2, baudrate=2500000, polarity=0, phase=0, sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))
              
# musim si prvně přečíst data z blocku, ten jde pouze přepsat. potřebuju je teda upravit a pak tam writenout novou verzi dat    
KEY = b'\xff\xff\xff\xff\xff\xff'
data_z_blocku,UID=read(4,KEY)
print(f"UID čipu: {UID}")

vysledna_data=bytes_to_ints(data_z_blocku)

index=1
for cas in vysledna_data:
    print(f"{index}/{len(vysledna_data)}: {cas}")
    index+=1