import time
import machine
import sys
import select

# Import modules
import sync_manager
import main_station_read

def main():
    print("==========================================")
    print("   ORIENTEERING MASTER STATION STARTED    ")
    print("==========================================")
    print("Commands:")
    print("  SYNC  - Start synchronization mode")
    print("  READ  - Start reading mode (finish line)")
    print("Waiting for command (5s timeout -> default READ)...")

    # Jednoduché čekání na příkaz z PC
    # Pokud PC nepošle nic do 5 sekund, spustí se READ mode (jako fallback)
    
    # Infinite loop waiting for command
    # We blink the internal LED to show we are waiting
    led = machine.Pin(2, machine.Pin.OUT) # Assuming LED on GPIO 2 (or 5)
    
    while True:
        # POUŽITÍ SELECT (dle původního funkčního stavu)
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            try:
                line = sys.stdin.readline()
                if line:
                    command = line.strip().upper()
                    print(f"Received command: '{command}'")
                    
                    if command == "SYNC":
                        start_sync_mode()
                        # If sync mode returns, we go back to waiting
                        #print("Returned from Sync Mode. Waiting for command...")
                        start_read_mode()
                    elif command == "READ":
                        start_read_mode()
                        # If read mode returns
                        print("Returned from Read Mode. Waiting for command...")
                    else:
                        print(f"Unknown command: {command}")
            except Exception:
                pass
        
        # Heartbeat blink
        led.value(not led.value())
        time.sleep(0.5)
        # print("Waiting for command (SYNC / READ)...")

def start_sync_mode():
    print("--- MODE: SYNCHRONIZATION ---")
    try:
        sync_manager.vysilat_cas_loop()
    except KeyboardInterrupt:
        print("Sync interrupted.")
        return

def start_read_mode():
    print("--- MODE: READING ---")
    try:
        main_station_read.start_reading()
    except KeyboardInterrupt:
        print("Reading interrupted.")
        return

if __name__ == "__main__":
    main()
