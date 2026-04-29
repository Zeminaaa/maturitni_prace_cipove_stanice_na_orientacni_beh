import time

import mfrc522      # https://github.com/cefn/micropython-mfrc522
from machine import Pin, SPI
from time import sleep_ms

import setup
import sync_manager


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
CARD_REMOVAL_TIMEOUT_MS = 2500


sck = Pin(SCK_PIN, Pin.OUT)
mosi = Pin(MOSI_PIN, Pin.OUT)
miso = Pin(MISO_PIN, Pin.IN)
cs = Pin(CS_PIN, Pin.OUT)
rst = Pin(RST_PIN, Pin.OUT)
rele = Pin(RELE_PIN, Pin.OUT)

vspi = None
rdr = None
STATION_ID = None


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
            print('[SLAVE] Reinit RC522 selhal:', ex)


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

        if rdr.auth(rdr.AUTHENT1A, target_block, key, raw_uid) != rdr.OK:
            return None, uid, 'auth'

        data = rdr.read(target_block)
        if data is None or len(data) < 16:
            return None, uid, 'read'

        return ['%02X' % b for b in data], uid, 'ok'
    except Exception as ex:
        return None, None, 'exception:%s' % type(ex).__name__
    finally:
        try:
            rdr.stop_crypto1()
        except Exception:
            pass


def _write_block_once(target_block, key, expected_uid, data_to_write):
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

        if rdr.auth(rdr.AUTHENT1A, target_block, key, raw_uid) != rdr.OK:
            return uid, 'auth'

        if rdr.write(target_block, data_to_write) == rdr.OK:
            return uid, 'ok'

        return uid, 'write'
    except Exception as ex:
        return None, 'exception:%s' % type(ex).__name__
    finally:
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


def _read_update_verify_once(target_block, key):
    try:
        stat, _tag_type = _request_tag()
        if stat != rdr.OK:
            return False, None, 'no_tag'

        stat, raw_uid = rdr.anticoll()
        if stat != rdr.OK or len(raw_uid) < 4:
            return False, None, 'anticoll'

        uid = _uid_to_text(raw_uid)

        if rdr.select_tag(raw_uid) != rdr.OK:
            return False, uid, 'select'

        if rdr.auth(rdr.AUTHENT1A, target_block, key, raw_uid) != rdr.OK:
            return False, uid, 'auth'

        data = rdr.read(target_block)
        if data is None or len(data) < 16:
            return False, uid, 'read'

        data_hex = ['%02X' % b for b in data]
        current_timestamp = _station_time_value()
        data_to_write = uprav_data(current_timestamp, data_hex)

        print('UID cipu: %s' % uid)
        print('Zapisuji cas: %s' % current_timestamp)

        if rdr.write(target_block, data_to_write) != rdr.OK:
            return False, uid, 'write'

        sleep_ms(25)
        verified = rdr.read(target_block)
        if verified is None or len(verified) < 16:
            return False, uid, 'verify_read'
        if bytes(verified) != data_to_write:
            return False, uid, 'verify_mismatch'

        return True, uid, 'ok'
    except Exception as ex:
        return False, None, 'exception:%s' % type(ex).__name__
    finally:
        try:
            rdr.stop_crypto1()
        except Exception:
            pass


def process_card_reliable(attempts=VERIFIED_WRITE_ATTEMPTS):
    last_uid = None
    last_reason = 'no_tag'

    for _attempt in range(attempts):
        ok, uid, reason = _read_update_verify_once(TARGET_BLOCK, KEY)
        if ok:
            setup.ano_sound()
            print('SUCCESS: Data zapsana a overena.')
            return True, uid, 'ok'

        if uid is not None:
            last_uid = uid
        last_reason = reason

        if reason == 'no_tag' and last_uid is None:
            break
        sleep_ms(RETRY_DELAY_MS)

    return False, last_uid, last_reason


def read(TARGET_BLOCK, KEY):
    failures = 0
    while True:
        rele.off()
        data, uid, reason = read_block_reliable(TARGET_BLOCK, KEY)

        if data is not None:
            print('Detekovano!')
            print('** BLOK %s USPESNE PRECTEN **' % TARGET_BLOCK)
            return data, uid

        if reason != 'no_tag':
            failures += 1
            print('[SLAVE] Cteni selhalo (%s), opakuji.' % reason)
            if failures >= RESET_AFTER_FAILURES:
                recover_reader()
                failures = 0
        else:
            failures = 0

        sleep_ms(IDLE_DELAY_MS)


def _station_time_value():
    # Na čipu jsou pro každou stanici jen 2 bajty, proto ukládáme jen zkrácenou časovou hodnotu.
    return int(time.time()) & 0xFFFF


def uprav_data(time_in_sec, data):
    if STATION_ID is None or STATION_ID < 1 or STATION_ID > 8:
        raise ValueError('STATION_ID musi byt v rozsahu 1-8')

    target1 = (STATION_ID * 2) - 2
    target2 = (STATION_ID * 2) - 1
    updated = list(data)

    bytes_val = int(time_in_sec & 0xFFFF).to_bytes(2, 'big')
    converted_time = ['%02X' % b for b in bytes_val]

    updated[target1] = converted_time[0]
    updated[target2] = converted_time[1]

    return bytes.fromhex(''.join(updated))


def write(TARGET_BLOCK, KEY, uid, data_z_blocku=None):
    if data_z_blocku is None:
        data_z_blocku, read_uid = read(TARGET_BLOCK, KEY)
        if read_uid != uid:
            setup.ne_sound()
            print('Prilozte stejny cip')
            return False

    current_timestamp = _station_time_value()
    print('Zapisuji cas: %s' % current_timestamp)
    data_to_write = uprav_data(current_timestamp, data_z_blocku)

    last_reason = 'unknown'
    for _attempt in range(VERIFIED_WRITE_ATTEMPTS):
        ok, reason = write_block_reliable(TARGET_BLOCK, KEY, uid, data_to_write)
        if not ok:
            last_reason = reason
            if reason != 'wrong_uid':
                recover_reader()
            sleep_ms(RETRY_DELAY_MS)
            continue

        verified_data, verified_uid, verified_reason = read_block_reliable(TARGET_BLOCK, KEY, attempts=4)
        if verified_uid == uid and verified_data is not None and bytes.fromhex(''.join(verified_data)) == data_to_write:
            setup.ano_sound()
            print('SUCCESS: Data zapsana do bloku %s.' % TARGET_BLOCK)
            return True

        last_reason = verified_reason
        sleep_ms(RETRY_DELAY_MS)

    setup.ne_sound()
    print('FAILED: Zapis nebo kontrola zapisu selhala (%s).' % last_reason)
    if last_reason != 'wrong_uid':
        recover_reader()
    return False


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


def process_one_card():
    failures = 0
    while True:
        rele.off()
        ok, uid, reason = process_card_reliable()
        if ok:
            rele.on()
            wait_for_card_removed()
            rele.off()
            return

        if uid is not None:
            setup.ne_sound()
            print('[SLAVE] Cip %s detekovan, ale zapis selhal (%s).' % (uid, reason))
            recover_reader()
            wait_for_card_removed()
            return

        if reason != 'no_tag':
            failures += 1
            print('[SLAVE] Cteni/zapis selhal (%s), cekam dal.' % reason)
            if failures >= RESET_AFTER_FAILURES:
                recover_reader()
                failures = 0
        else:
            failures = 0

        sleep_ms(IDLE_DELAY_MS)


def main():
    global STATION_ID

    sync_manager.cekat_na_sync()
    print('--- CAS NASTAVEN ---')

    setup.bud_zticha()
    STATION_ID = setup.station_id()
    print('id stanice je: %s' % STATION_ID)

    init_reader()

    failures = 0
    while True:
        try:
            process_one_card()
            failures = 0
        except KeyboardInterrupt:
            print('Bye')
            break
        except Exception as ex:
            failures += 1
            print('[SLAVE] Chyba hlavni smycky: %s' % ex)
            if failures >= RESET_AFTER_FAILURES:
                recover_reader()
                failures = 0
            sleep_ms(500)


if __name__ == '__main__':
    main()
