# Čipové stanice pro orientační běh

Tento repozitář obsahuje jen soubory potřebné pro běh stanic na `ESP32`.

## Důležitá poznámka k autorství

Soubor `mfrc522.py` **není mým autorským dílem**. Jde o převzatou externí knihovnu pro práci s RFID čtečkou `RC522`.

Původní zdroj:

`https://github.com/cefn/micropython-mfrc522`

Ostatní zde uvedené soubory jsou součástí mého vlastního projektu.

## Použité soubory

Projekt v této podobě používá pouze tyto soubory:

- `main_station_read.py`
- `master_main.py`
- `slave_main.py`
- `sync_manager.py`
- `web_server.py`
- `mfrc522.py`

## Který soubor patří na kterou stanici

### Master stanice

Na master stanici se nahrávají tyto soubory:

- `master_main.py`
- `main_station_read.py`
- `sync_manager.py`
- `web_server.py`
- `mfrc522.py`

Po nahrání je potřeba soubor `master_main.py` na zařízení **přejmenovat na `main.py`**. Teprve pod tímto názvem se po spuštění desky automaticky vykoná.

### Slave stanice

Na každou slave stanici se nahrávají tyto soubory:

- `slave_main.py`
- `sync_manager.py`
- `mfrc522.py`

Po nahrání je potřeba soubor `slave_main.py` na zařízení **přejmenovat na `main.py`**. Teprve pod tímto názvem se po spuštění desky automaticky vykoná.

## Stručná role jednotlivých souborů

- `master_main.py`  
  Hlavní program pro master stanici. Spouští Wi-Fi, webové rozhraní a řídí režimy synchronizace a cílového čtení.

- `main_station_read.py`  
  Programová část pro master stanici v cíli. Čte čipy, získává uložené časy a po úspěšném zpracování čip maže.

- `slave_main.py`  
  Hlavní program pro slave stanici. Po synchronizaci času zapisuje průchody závodníků do RFID čipu.

- `sync_manager.py`  
  Společná logika synchronizace času mezi stanicemi pomocí `ESP-NOW`.

- `web_server.py`  
  Webové rozhraní běžící na master stanici. Slouží k ovládání závodu a zobrazení výsledků.

- `mfrc522.py`  
  Převzatá knihovna pro komunikaci s RFID čtečkou `RC522`.

## Důležité upozornění

Na jednom zařízení může být vždy jen jedna varianta hlavního programu:

- na masteru jako `main.py` běží původně `master_main.py`,
- na slave jako `main.py` běží původně `slave_main.py`.

Soubor `main.py` tedy nevzniká ručně zvlášť, ale přejmenováním správného hlavního souboru podle role konkrétní stanice.
