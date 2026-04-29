import time
import gc

import mfrc522      # https://github.com/cefn/micropython-mfrc522
from machine import Pin, SPI
from time import sleep_ms

import setup


KEY = b'\xff\xff\xff\xff\xff\xff'
TARGET_BLOCK = 4

SCK_PIN = 18
MOSI_PIN = 23
MISO_PIN = 19
CS_PIN = 5
RST_PIN = 17
RELE_PIN = 2  # Historický pin. V aktuálním hardware na něm nic není.
SPI_BAUDRATE = 25000
READ_RETRY_ATTEMPTS = 12
WRITE_RETRY_ATTEMPTS = 12
VERIFIED_WRITE_ATTEMPTS = 3
RETRY_DELAY_MS = 45
IDLE_DELAY_MS = 80
RESET_AFTER_FAILURES = 20
SAME_CARD_COOLDOWN_MS = 1800
CARD_REMOVAL_TIMEOUT_MS = 2500
RECOVER_AFTER_CARD = True
ZERO_BLOCK = bytes(16)


sck = Pin(SCK_PIN, Pin.OUT)
mosi = Pin(MOSI_PIN, Pin.OUT)
miso = Pin(MISO_PIN, Pin.IN)
cs = Pin(CS_PIN, Pin.OUT)
rst = Pin(RST_PIN, Pin.OUT)
rele = Pin(RELE_PIN, Pin.OUT)

vspi = None
rdr = None


def _ticks_ms():
    try:
        return time.ticks_ms()
    except AttributeError:
        return int(time.time() * 1000)


def _ticks_diff(new, old):
    try:
        return time.ticks_diff(new, old)
    except AttributeError:
        return new - old


def reset_sensor(pin_number=RST_PIN):
    """Hard-reset RC522 přes RST pin."""
    pin = pin_number if hasattr(pin_number, 'value') else Pin(pin_number, Pin.OUT)
    print('Resetuji RC522...')
    pin.value(0)
    sleep_ms(150)
    pin.value(1)
    sleep_ms(250)


def init_reader():
    global vspi, rdr
    cs.value(1)
    reset_sensor(rst)
    vspi = SPI(2, baudrate=SPI_BAUDRATE, polarity=0, phase=0, sck=sck, mosi=mosi, miso=miso)
    rdr = mfrc522.MFRC522(spi=vspi, gpioRst=RST_PIN, gpioCs=CS_PIN)
    sleep_ms(50)
    return rdr


def recover_reader():
    cs.value(1)
    reset_sensor(rst)
    if rdr is not None:
        try:
            rdr.init()
            sleep_ms(50)
        except Exception as ex:
            print('[READ] Reinit RC522 selhal:', ex)
    gc.collect()


def bytes_to_ints(data):
    result = []
    for index in range(0, len(data), 2):
        hex_pair = data[index] + data[index + 1]
        result.append(str(int(hex_pair, 16)))
    return result


def _station_time_value():
    # Stejný zkrácený časový formát jako na slave stanicích.
    return int(time.time()) & 0xFFFF


def _uid_to_text(raw_uid):
    return '%02X-%02X-%02X-%02X' % (raw_uid[0], raw_uid[1], raw_uid[2], raw_uid[3])


def _cleanup_card_session():
    try:
        rdr.halt_a()
    except Exception:
        pass
    try:
        rdr.stop_crypto1()
    except Exception:
        pass


def _request_tag():
    stat, tag_type = rdr.request(rdr.REQIDL)
    if stat != rdr.OK:
        stat, tag_type = rdr.request(rdr.REQALL)
    return stat, tag_type


def _read_block_once(target_block, key):
    selected = False
    try:
        stat, _tag_type = _request_tag()
        if stat != rdr.OK:
            return None, None, 'no_tag'

        stat, raw_uid = rdr.anticoll()
        if stat != rdr.OK or len(raw_uid) < 4:
            return None, None, 'anticoll'

        uid = _uid_to_text(raw_uid)

        if rdr.select_tag(raw_uid) != rdr.OK:
            return None, uid, 'select'
        selected = True

        if rdr.auth(rdr.AUTHENT1A, target_block, key, raw_uid) != rdr.OK:
            return None, uid, 'auth'

        data = rdr.read(target_block)
        if data is None or len(data) < 16:
            return None, uid, 'read'

        return ['%02X' % b for b in data], uid, 'ok'
    except Exception as ex:
        return None, None, 'exception:%s' % type(ex).__name__
    finally:
        if selected:
            _cleanup_card_session()
        else:
            try:
                rdr.stop_crypto1()
            except Exception:
                pass


def _write_block_once(target_block, key, expected_uid, data_to_write):
    selected = False
    try:
        stat, _tag_type = _request_tag()
        if stat != rdr.OK:
            return None, 'no_tag'

        stat, raw_uid = rdr.anticoll()
        if stat != rdr.OK or len(raw_uid) < 4:
            return None, 'anticoll'

        uid = _uid_to_text(raw_uid)
        if uid != expected_uid:
            return uid, 'wrong_uid'

        if rdr.select_tag(raw_uid) != rdr.OK:
            return uid, 'select'
        selected = True

        if rdr.auth(rdr.AUTHENT1A, target_block, key, raw_uid) != rdr.OK:
            return uid, 'auth'

        if rdr.write(target_block, data_to_write) == rdr.OK:
            return uid, 'ok'

        return uid, 'write'
    except Exception as ex:
        return None, 'exception:%s' % type(ex).__name__
    finally:
        if selected:
            _cleanup_card_session()
        else:
            try:
                rdr.stop_crypto1()
            except Exception:
                pass


def read_block_reliable(target_block, key, attempts=READ_RETRY_ATTEMPTS):
    last_uid = None
    last_reason = 'no_tag'

    for _attempt in range(attempts):
        data, uid, reason = _read_block_once(target_block, key)
        if data is not None:
            return data, uid, 'ok'

        if uid is not None:
            last_uid = uid
        last_reason = reason

        if reason == 'no_tag' and last_uid is None:
            break
        sleep_ms(RETRY_DELAY_MS)

    return None, last_uid, last_reason


def write_block_reliable(target_block, key, expected_uid, data_to_write, attempts=WRITE_RETRY_ATTEMPTS):
    last_reason = 'no_tag'

    for _attempt in range(attempts):
        uid, reason = _write_block_once(target_block, key, expected_uid, data_to_write)
        if reason == 'ok':
            return True, 'ok'
        if reason == 'wrong_uid':
            return False, 'wrong_uid'

        last_reason = reason
        sleep_ms(RETRY_DELAY_MS)

    return False, last_reason


def _card_present():
    try:
        stat, _tag_type = _request_tag()
        return stat == rdr.OK
    except Exception:
        return False


def wait_for_card_removed(timeout_ms=CARD_REMOVAL_TIMEOUT_MS):
    start = _ticks_ms()
    while _ticks_diff(_ticks_ms(), start) < timeout_ms:
        if not _card_present():
            return True
        sleep_ms(60)
    return False


def wipe_card_block(expected_uid, target_block=TARGET_BLOCK, key=KEY):
    last_reason = 'unknown'
    try:
        for _attempt in range(VERIFIED_WRITE_ATTEMPTS):
            ok, reason = write_block_reliable(target_block, key, expected_uid, ZERO_BLOCK)
            if not ok:
                last_reason = reason
                if reason != 'wrong_uid':
                    recover_reader()
                sleep_ms(RETRY_DELAY_MS)
                continue

            data, uid, reason = read_block_reliable(target_block, key, attempts=4)
            if uid == expected_uid and data is not None and all(value == '00' for value in data):
                print('[READ] Cip %s wipnut.' % expected_uid)
                return True

            last_reason = reason
            sleep_ms(RETRY_DELAY_MS)
    finally:
        if RECOVER_AFTER_CARD:
            recover_reader()

    print('[READ] Wipe selhal (%s).' % last_reason)
    return False


def read(TARGET_BLOCK, KEY):
    failures = 0
    while True:
        rele.off()
        data, uid, reason = read_block_reliable(TARGET_BLOCK, KEY)

        if data is not None:
            rele.on()
            print('Detekovano!')
            print('** BLOK %s USPESNE PRECTEN **' % TARGET_BLOCK)
            return data, uid

        if reason != 'no_tag':
            failures += 1
            print('[READ] Pokus selhal (%s), cekam dal.' % reason)
            if failures >= RESET_AFTER_FAILURES:
                recover_reader()
                failures = 0
        else:
            failures = 0

        sleep_ms(IDLE_DELAY_MS)


def _timestamp_text():
    try:
        lt = time.localtime()
        return '%02d:%02d:%02d' % (lt[3], lt[4], lt[5])
    except Exception:
        return '??:??:??'


def start_reading():
    if rdr is None:
        init_reader()

    print('[MAIN] Spoustim rezim cteni (Reading Mode)...')

    while True:
        try:
            data_z_blocku, uid = read(TARGET_BLOCK, KEY)
            print('UID cipu: %s' % uid)

            vysledna_data = bytes_to_ints(data_z_blocku)
            for index, cas in enumerate(vysledna_data, start=1):
                print('%s/%s: %s' % (index, len(vysledna_data), cas))

        except KeyboardInterrupt:
            print('[MAIN] Ukoncuji cteni.')
            break
        except Exception as ex:
            print('[MAIN] Chyba: %s' % ex)
            recover_reader()
            sleep_ms(500)


class ReadManager:
    """
    Neblokující čtečka pro hlavní smyčku masteru.

    Vrací slovník s UID, mezičasy a časem čtení, aby ho web mohl rovnou
    zapsat do tabulky.
    """

    KEY = KEY
    TARGET_BLOCK = TARGET_BLOCK

    def __init__(self):
        init_reader()
        self._last_uid = None
        self._last_read_ms = 0
        self._failures = 0
        self._locked_uid = None
        self._pending_wipe_uid = None
        print('[READ] ReadManager inicializovan.')

    def tick(self):
        if self._locked_uid is not None:
            if not _card_present():
                self._locked_uid = None
                if RECOVER_AFTER_CARD:
                    recover_reader()
            return None

        data, uid, reason = read_block_reliable(self.TARGET_BLOCK, self.KEY)
        if data is None:
            if reason != 'no_tag':
                self._failures += 1
                print('[READ] Pokus selhal (%s), cekam dal.' % reason)
                if self._failures >= RESET_AFTER_FAILURES:
                    recover_reader()
                    self._failures = 0
            return None

        self._failures = 0
        now = _ticks_ms()
        if uid == self._last_uid and _ticks_diff(now, self._last_read_ms) < SAME_CARD_COOLDOWN_MS:
            return None

        self._last_uid = uid
        self._last_read_ms = now
        self._pending_wipe_uid = uid
        self._locked_uid = uid

        times = bytes_to_ints(data)
        master_time = str(_station_time_value())
        result = {
            'uid': uid,
            'times': times,
            'ts': _timestamp_text(),
            'master_time': master_time,
        }
        print('[READ] Cip %s precten. Casy: %s  MASTER: %s' % (uid, times, master_time))
        try:
            setup.ano_sound()
        except Exception as ex:
            print('[READ] Zvuk po precteni selhal: %s' % ex)
        gc.collect()
        return result

    def wipe_last_card(self):
        if self._pending_wipe_uid is None:
            return False
        uid = self._pending_wipe_uid
        self._pending_wipe_uid = None
        return wipe_card_block(uid, self.TARGET_BLOCK, self.KEY)


setup.bud_zticha()


if __name__ == '__main__':
    start_reading()
