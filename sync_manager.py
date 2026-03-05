import network
import espnow
import struct
import time
import machine
import setup
import sys
import select

# --- NASTAVENÍ HARDWARU ---
# LED pro indikaci čekání (Lolin=5, DevKit=2)
# Pokud máš definovanou LED i v setup.py, použij setup.led
LED_PIN_NUM = 5

def cekat_na_sync():
    led = machine.Pin(LED_PIN_NUM, machine.Pin.OUT)
    
    # 1. Start WiFi (jen pro ESP-NOW)
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    # Odpojíme se od případných AP, abychom mohli měnit kanál
    sta.disconnect() 
    
    try:
        sta.config(channel=1)
    except Exception as e:
        print(f"[SYNC ERROR] Failed to set channel: {e}")

    print(f"[SYNC] WiFi Channel set to: {sta.config('channel')}")

    e = espnow.ESPNow()
    e.active(True)
    
    # DŮLEŽITÉ: Musíme přidat broadcast peer, abychom mohli posílat ACK
    broadcast = b'\xff' * 6
    try:
        e.add_peer(broadcast)
    except:
        pass
    
    print("[SYNC] Čekám na signál od Mastera (ESP-NOW)...")
    
    is_synced = False
    
    # Blink variables
    last_blink = 0
    led_state = 0
    
    while not is_synced:
        # 1. Listen (Aggressive)
        # We listen in short bursts to allow for LED updates, 
        # but we want to spend most time here.
        try:
            # Timeout 200ms
            host, msg = e.recv(200) 
            if msg:
                print(f"[SYNC] Received from {host}")
                try:
                    received_epoch = struct.unpack('I', msg)[0]
                    
                    tm = time.localtime(received_epoch)
                    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
                    
                    print(f"[SYNC] ÚSPĚCH! Čas nastaven: {tm[3]:02}:{tm[4]:02}:{tm[5]:02}")
                    is_synced = True
                except Exception as ex:
                    print(f"[SYNC] Parse error: {ex}")
        except OSError:
            pass # Timeout
            
        # 2. Handle LED (Non-blocking Blink)
        now = time.ticks_ms()
        if time.ticks_diff(now, last_blink) > 250: # Blink every 250ms
            led_state = not led_state
            led.value(led_state)
            last_blink = now

    # 2. Odeslat potvrzení (ACK) Masterovi
    # Posíláme HNED a OPAKOVANĚ (Redundancy)
    print("--- SENDING ACK ---")
    try:
        my_id = setup.station_id()
        msg = b'ACK' + bytes([my_id])
        
        print(f"[SYNC] Odesílám ACK (ID {my_id}) 5x...")
        for _ in range(5):
            e.send(broadcast, msg)
            time.sleep(0.05) 
            
    except Exception as e:
        print(f"[SYNC] Chyba odeslání ACK: {e}")

    # 3. Úklid
    try:
        e.active(False)
        sta.active(False)
    except:
        pass
    
    # 4. Oslavná fanfára
    led.value(0) 
    print("[SYNC] Přehrávám potvrzení...")
    try:
        setup.sync_confirm()
    except Exception as e:
        print(f"Buzzer error: {e}")
        
    print("[SYNC] Hotovo. Předávám řízení aplikaci.")

def vysilat_cas_loop():
    """
    Tato funkce běží v nekonečné smyčce a vysílá čas.
    Používá se na Master stanici na startu.
    Umožňuje naslouchat na potvrzení od stanic (ACK).
    """
    led = machine.Pin(LED_PIN_NUM, machine.Pin.OUT)

    # 1. Start WiFi
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()
    
    try:
        sta.config(channel=1)
    except:
        pass
        
    print(f"[MASTER] WiFi Channel: {sta.config('channel')}")

    e = espnow.ESPNow()
    e.active(True)

    # Přidat broadcast peer (FF:FF:FF:FF:FF:FF)
    broadcast_mac = b'\xff' * 6
    try:
        e.add_peer(broadcast_mac)
    except:
        pass

    print("[MASTER] Začínám vysílat čas. Připojte ostatní desky.")
    print("-----------------------------------------------------")

    # Kolikrát za sekundu kontrolovat příchozí zprávy
    # Polling rate doesn't matter much if we drain the buffer
    last_send_time = 0

    while True:
        current_time = time.time()
        
        # A) Vysílání času (jednou za sekundu)
        if current_time - last_send_time >= 1.0:
            msg = struct.pack('I', int(current_time))
            try:
                e.send(broadcast_mac, msg)
                # Vizuální kontrola v konzoli (pro Race Manager parse)
                # Formát: [MASTER] Odesláno: HH:MM:SS
                t = time.localtime(current_time)
                print(f"[MASTER] Odesláno: {t[3]:02}:{t[4]:02}:{t[5]:02}")
                
                led.value(0)
                time.sleep(0.05)
                led.value(1)
            except OSError as err:
                 pass
            last_send_time = current_time

        # B) Naslouchání na odpovědi (ACK)
        # Check ALL messages in buffer
        while True:
            try:
                # 0 timeout = non-blocking
                host, msg = e.recv(0) 
                if msg:
                     if msg.startswith(b'ACK'):
                        try:
                            station_id = msg[3]
                            # Formát pro PC aplikaci: "SYNCED: <ID>"
                            print(f"SYNCED: {station_id}")
                        except IndexError:
                            pass
                else:
                    # No more messages
                    break
            except OSError:
                break

        # C) Naslouchání na příkazy z PC (přes sériovou linku)
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            try:
                line = sys.stdin.readline()
                if line:
                    command = line.strip().upper()
                    if command == "READ":
                        print("[MASTER] Přijat příkaz READ z PC. Ukončuji synchronizaci.")
                        break
            except Exception:
                pass

        # Krátká pauza pro uvolnění CPU
        time.sleep_ms(50)
