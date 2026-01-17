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

# získání id stanice, bude se hodit pro zápis na konkrétní místa v blocku se kterým pracuju        
STATION_ID=setup.station_id()
print(f"id stanice je: {STATION_ID}") 

def reset_sensor(pin_number):
    """Provede tvrdý reset RC522 modulu."""
    print("Resetuji RC522...")
    rst = Pin(pin_number, Pin.OUT)
    
    rst.value(0)       # Vypnutí (Active Low)
    sleep_ms(50)  # Krátká pauza pro jistotu
    rst.value(1)       # Zapnutí
    sleep_ms(50)  # Čas na nastartování čtečky


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
                print('uid: %02X-%02X-%02X-%02X' % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3]))
                
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
                                setup.ano_sound()
                                print(f'** BLOK {TARGET_BLOCK} USPESNE PRECTEN **')
                                # Data vypisujeme v HEX, aby byla vidět i binární data z vašeho zápisu
                                return(['%02X' % b for b in data])
                                
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
                
                
def uprav_data(time_in_sec,data):
    target1=(STATION_ID*2)-2
    target2=(STATION_ID*2)-1
    print(f"cílové jsou: {target1} a {target2}")
    
    # Convert integer to bytes (2 bytes, big-endian)
    bytes_val = time_in_sec.to_bytes(2, 'big')
    # Format each byte as a 2-digit hex string and put into a list
    converted_time = [f'{b:02x}' for b in bytes_val]
    print(converted_time)
    
    data[target1]=converted_time[0]
    data[target2]=converted_time[1]
    
    DATA_TO_WRITE = bytes.fromhex("".join(data))
    return DATA_TO_WRITE

def write(TARGET_BLOCK,KEY,data):
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
                            
                        print(f"** Trying Block {TARGET_BLOCK} **")
                            
                        # 1. AUTENTIZACE
                        if rdr.auth(rdr.AUTHENT1A, TARGET_BLOCK, KEY, raw_uid) == rdr.OK:
                            print(f"  -> Authentication success for Block {TARGET_BLOCK}.")

                            # 2. ZÁPIS DAT
                            stat_w = rdr.write(TARGET_BLOCK, data)
                            
                            rdr.stop_crypto1() # Zastavit šifrování ihned po zápisu
                            
                            if stat_w == rdr.OK:
                                print(f"  -> SUCCESS: Data written to Block {TARGET_BLOCK}.")
                            else:
                                print(f"  -> FAILED: Could not write data to Block {TARGET_BLOCK}.")
                        else:
                            print(f"  -> ERROR: Authentication failed for Block {TARGET_BLOCK}.")
                            rdr.stop_crypto1() # Zastavit šifrování
                        
                        # Krátká pauza, po které uživatel kartu odebere a znovu přiloží
                        sleep_ms(2000)
                        print("\nPrilozte kartu")
                    else:
                        print("Failed to select tag")

    except KeyboardInterrupt:
        print("Bye")
                
# tohle resetuje čtečku čipů, protože po startupu často vubec nereaguje             
reset_sensor(rst)
spi = SPI(2, baudrate=2500000, polarity=0, phase=0, sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))
              
# musim si prvně přečíst data z blocku, ten jde pouze přepsat. potřebuju je teda upravit a pak tam writenout novou verzi dat    
KEY = b'\xff\xff\xff\xff\xff\xff'
data_z_blocku=read(4,KEY)
print(data_z_blocku)
zapisova_data=uprav_data(356,data_z_blocku)
write(4,KEY,zapisova_data)
