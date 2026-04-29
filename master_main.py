"""
Hlavní program pro master stanici.

Master vytvoří vlastní Wi-Fi síť, spustí webové rozhraní a podle stavu
závodu přepíná mezi synchronizací a čtením čipů v cíli.
"""

import time
import gc
import machine
import network

from web_server import WebServer
from sync_manager import MasterSyncManager
from main_station_read import ReadManager

AP_SSID     = 'OrientacniBeh'
AP_PASSWORD = 'start1234'      # min. 8 znaků, nebo '' pro otevřenou síť
AP_CHANNEL  = 1                # Musí odpovídat kanálu ESP-NOW na Slave
HEARTBEAT_PIN = None           # Samostatná heartbeat LED se v aktuálním hardware nepoužívá.

def make_state():
    return {
        'mode':         'IDLE',   # 'IDLE' | 'SYNCING' | 'READING'
        'num_stations': 0,
        'synced_ids':   set(),
        'chip_readings': [],
        'log':          [],
    }

def _log(state, msg):
    print(msg)
    log = state['log']
    log.append(msg)
    if len(log) > 200:
        del log[:50]

# ---------------------------------------------------------------------------
def setup_wifi(state):
    """Spustí AP + STA (STA potřebuje ESP-NOW)."""
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(
        essid=AP_SSID,
        password=AP_PASSWORD,
        channel=AP_CHANNEL,
        authmode=3 if AP_PASSWORD else 0,  # 3 = WPA2, 0 = otevřená
    )

    # STA rozhraní je potřeba kvůli ESP-NOW. K žádné jiné síti se nepřipojuje.
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        sta.disconnect()
    except Exception:
        pass

    deadline = time.ticks_ms() + 3000
    while not ap.active():
        if time.ticks_diff(time.ticks_ms(), deadline) > 0:
            break
        time.sleep_ms(100)

    ip = ap.ifconfig()[0]
    _log(state, f'[MASTER] WiFi AP aktivan. SSID: {AP_SSID}  IP: {ip}  Kanal: {AP_CHANNEL}')
    return ap, sta

def main():
    print('==========================================')
    print('  ORIENTEERING MASTER STATION (WEB MODE) ')
    print('==========================================')

    state = make_state()

    ap, sta = setup_wifi(state)

    web = WebServer(state)

    _log(state, f'Připojte se k WiFi "{AP_SSID}" a otevřete http://192.168.4.1')
    _log(state, '[MASTER] Přístup přes běžný prohlížeč. Captive portal je vypnutý kvůli stabilitě připojení.')

    led = machine.Pin(HEARTBEAT_PIN, machine.Pin.OUT) if HEARTBEAT_PIN is not None else None

    # Manažery se vytvářejí až ve chvíli, kdy jsou opravdu potřeba.
    sync_mgr = None
    read_mgr  = None
    last_blink = 0
    last_gc = time.ticks_ms()

    while True:
        web.handle()

        if state.pop('sync_reset_requested', False):
            if sync_mgr is not None:
                sync_mgr.cleanup()
                sync_mgr = None
            read_mgr = None

        mode = state['mode']

        if mode == 'SYNCING':
            read_mgr = None
            if sync_mgr is None:
                _log(state, f'[MASTER] Spouštím synchronizaci pro {state["num_stations"]} stanic.')
                sync_mgr = MasterSyncManager(state['num_stations'])

            done = sync_mgr.tick()

            state['synced_ids'] = sync_mgr.synced_ids

            # Stav se propisuje i do logu, aby byl hned vidět ve webu.
            for sid in sync_mgr.synced_ids:
                entry = f'[OK] Stanice {sid} synchronizována ({len(sync_mgr.synced_ids)}/{state["num_stations"]})'
                if entry not in state['log']:
                    _log(state, entry)

            if done:
                _log(state, '[OK] Synchronizace dokončena! Přepínám do READ.')
                sync_mgr = None
                state['mode'] = 'READING'
                state['synced_epoch'] = int(time.time())
                time.sleep_ms(200)
                read_mgr = ReadManager()
                web.sync_state(force=True)

        elif mode == 'READING':
            if read_mgr is None:
                read_mgr = ReadManager()

            result = read_mgr.tick()
            if result is not None:
                state['chip_readings'].append(result)
                _log(state, f'[OK] Čip přečten: UID={result["uid"]}  časy={result["times"]}')
                web.sync_state()
                if read_mgr.wipe_last_card():
                    _log(state, f'[OK] Čip vymazán: UID={result["uid"]}')
                else:
                    _log(state, f'[WARN] Čip se nepodařilo vymazat: UID={result["uid"]}')

        else:
            if sync_mgr is not None:
                sync_mgr.cleanup()
                sync_mgr = None
            read_mgr = None

        now = time.ticks_ms()
        if led is not None and time.ticks_diff(now, last_blink) >= 500:
            led.value(not led.value())
            last_blink = now

        # Průběžný úklid paměti, aby se hlavní smyčka zbytečně nenafukovala.
        if time.ticks_diff(now, last_gc) >= 5000:
            gc.collect()
            last_gc = now

        time.sleep_ms(10)


if __name__ == '__main__':
    main()
