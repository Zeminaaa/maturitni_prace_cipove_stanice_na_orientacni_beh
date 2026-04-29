import network
import espnow
import struct
import time
import machine
import setup
import sys
import select

# Samostatná LED pro sync se v aktuálním hardware nepoužívá.
LED_PIN_NUM = None


class _NoLed:
    def value(self, _value=None):
        return 0


def _sync_led():
    if LED_PIN_NUM is None:
        return _NoLed()
    return machine.Pin(LED_PIN_NUM, machine.Pin.OUT)

def cekat_na_sync():
    led = _sync_led()

    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect() 
    
    try:
        sta.config(channel=1)
    except Exception as e:
        print(f"[SYNC ERROR] Failed to set channel: {e}")

    print(f"[SYNC] WiFi Channel set to: {sta.config('channel')}")

    e = espnow.ESPNow()
    e.active(True)
    
    # Bez broadcast peeru by slave nedokázal poslat potvrzení zpět masteru.
    broadcast = b'\xff' * 6
    try:
        e.add_peer(broadcast)
    except:
        pass
    
    print("[SYNC] Čekám na signál od Mastera (ESP-NOW)...")
    
    is_synced = False
    
    last_blink = 0
    led_state = 0
    
    while not is_synced:
        try:
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
            pass

        now = time.ticks_ms()
        if time.ticks_diff(now, last_blink) > 250:
            led_state = not led_state
            led.value(led_state)
            last_blink = now

    # ACK se posílá několikrát za sebou, aby ho master snáz zachytil.
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

    try:
        e.active(False)
        sta.active(False)
    except:
        pass
    
    led.value(0) 
    print("[SYNC] Přehrávám potvrzení...")
    try:
        setup.sync_confirm()
    except Exception as e:
        print(f"Buzzer error: {e}")
        
    print("[SYNC] Hotovo. Předávám řízení aplikaci.")

def vysilat_cas_loop(num_stations=0):
    """
    Jednoduchá blokující synchronizace pro starší způsob ovládání.

    Master vysílá čas a zároveň čeká na ACK od slave stanic. Pokud je zadaný
    počet stanic, smyčka skončí sama po přijetí všech potvrzení.
    """
    led = _sync_led()

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

    broadcast_mac = b'\xff' * 6
    try:
        e.add_peer(broadcast_mac)
    except:
        pass

    print("[MASTER] Začínám vysílat čas. Připojte ostatní desky.")
    print("-----------------------------------------------------")

    last_send_time = 0
    synced_ids = set()

    while True:
        current_time = time.time()
        
        if current_time - last_send_time >= 1.0:
            msg = struct.pack('I', int(current_time))
            try:
                e.send(broadcast_mac, msg)
                t = time.localtime(current_time)
                print(f"[MASTER] Odesláno: {t[3]:02}:{t[4]:02}:{t[5]:02}")
                
                led.value(0)
                time.sleep(0.05)
                led.value(1)
            except OSError as err:
                 pass
            last_send_time = current_time

        while True:
            try:
                host, msg = e.recv(0) 
                if msg:
                     if msg.startswith(b'ACK'):
                        try:
                            station_id = msg[3]
                            if station_id not in synced_ids:
                                synced_ids.add(station_id)
                                print(f"SYNCED: {station_id}")
                                print(f"[MASTER] Synchronizovano: {len(synced_ids)}/{num_stations}")
                        except IndexError:
                            pass
                else:
                    break
            except OSError:
                break

        if num_stations > 0 and len(synced_ids) >= num_stations:
            print(f"[MASTER] Vsechny stanice ({num_stations}) synchronizovany. Prepinani do READ.")
            break

        time.sleep_ms(50)


class MasterSyncManager:
    """
    Neblokující synchronizace pro webový režim master stanice.

    Objekt se volá opakovaně z hlavní smyčky. Wi-Fi rozhraní už musí být
    připravené před vytvořením instance.
    """

    def __init__(self, num_stations):
        self.num_stations = num_stations
        self.synced_ids = set()
        self.done = False
        self.led = _sync_led()
        self._last_send = 0
        self._broadcast = b'\xff' * 6

        self._e = espnow.ESPNow()
        self._e.active(True)
        try:
            self._e.add_peer(self._broadcast)
        except Exception:
            pass

        print(f'[SYNC] MasterSyncManager init pro {num_stations} stanic.')

    def tick(self):
        """
        Provede jeden krok synchronizace.

        Vrací True ve chvíli, kdy jsou potvrzené všechny očekávané stanice.
        """
        if self.done:
            return True

        current = time.time()

        if current - self._last_send >= 1.0:
            msg = struct.pack('I', int(current))
            try:
                self._e.send(self._broadcast, msg)
                t = time.localtime(current)
                print(f'[MASTER] Odesláno: {t[3]:02}:{t[4]:02}:{t[5]:02}')
            except OSError:
                pass
            self.led.value(0)
            self._last_send = current

        while True:
            try:
                host, msg = self._e.recv(0)
                if msg:
                    if msg.startswith(b'ACK'):
                        try:
                            sid = msg[3]
                            if sid not in self.synced_ids:
                                self.synced_ids.add(sid)
                                print(f'SYNCED: {sid}')
                                print(f'[MASTER] Synchronizováno: {len(self.synced_ids)}/{self.num_stations}')
                        except IndexError:
                            pass
                else:
                    break
            except OSError:
                break

        if self.num_stations > 0 and len(self.synced_ids) >= self.num_stations:
            print(f'[MASTER] Všechny stanice ({self.num_stations}) synchronizovány. Přepínám do READ.')
            self.done = True
            self.cleanup()
            return True

        return False

    def cleanup(self):
        """Uklidí ESP-NOW, ale nechá běžet Wi-Fi rozhraní."""
        try:
            self._e.active(False)
        except Exception:
            pass
        print('[SYNC] Cleanup hotov.')
