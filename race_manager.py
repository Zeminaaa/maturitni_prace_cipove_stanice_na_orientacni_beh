import serial
import serial.tools.list_ports
import time
import sys

def list_ports():
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def main():
    print("===========================================")
    print("   ORIENTEERING RACE MANAGER (PC HOST)     ")
    print("===========================================")

    # 1. Select Port
    ports = list_ports()
    if not ports:
        print("No serial ports found! Connect the Master station.")
        return

    print("Available ports:")
    for i, p in enumerate(ports):
        print(f"  {i+1}. {p}")
    
    try:
        idx = int(input("Select port (number): ")) - 1
        port = ports[idx]
    except:
        port = ports[0]
        print(f"Invalid selection, using {port}")

    # 2. Configuration
    try:
        num_stations = int(input("Enter number of stations to sync (e.g. 5): "))
    except:
        num_stations = 1
    
    print(f"Connecting to {port}...")
    
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(2) # Wait for connection
        
        # Reset board via DTR/RTS
        # Standard ESP32 Reset: EN=Low(DTR), IO0=High(RTS) -> Boot
        # We toggle DTR to reset
        ser.dtr = False
        ser.rts = False
        time.sleep(0.1)
        
        print("Resetting board...")
        # Pulse DTR to reset
        ser.dtr = True
        time.sleep(0.2)
        ser.dtr = False
        ser.rts = False # Ensure we don't hold reset or boot mode
        
        time.sleep(1) # Wait for boot
        
        print("Reading boot messages (3s)...")
        start_wait = time.time()
        while time.time() - start_wait < 3.0:
            if ser.in_waiting > 0:
                try:
                    line = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    print(line, end='')
                except:
                    pass
            time.sleep(0.1)
        
        print("\n\n--- STARTING SYNCHRONIZATION ---")
        synced_ids = set()
        
        # Check current state/menu
        ser.write(b'\n') # Wake up REPL if needed

        # 3. Synchronize
        print("\n--- STARTING SYNCHRONIZATION ---")
        synced_ids = set()
        
        # We need to send the "SYNC" command when the board asks for it.
        # Or validly just send it repeatedly until we see output.
        
        print("Sending SYNC command...")
        
        # Send SYNC command repeatedly until we get a response or user stops
        # Also print everything we receive to debug what the board is doing
        
        start_time = time.time()
        last_send = 0
        
        while len(synced_ids) < num_stations:
            # Send SYNC every 2 seconds
            print("právě jsem začal loop, protože len synced_ids je menší než num_stations, viz níže")
            print(f"synced_ids: {synced_ids}")
            print(f"Délka synced_ids: {len(synced_ids)}")
            if time.time() - last_send > 2.0:
                print("-> Sending SYNC...")
                ser.write(b"SYNC\n")
                last_send = time.time()
            
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(f"[DEVICE] {line}")
                        
                        if "SYNCED:" in line:
                            try:
                                parts = line.split(":")
                                station_id = int(parts[1].strip())
                                if station_id not in synced_ids:
                                    synced_ids.add(station_id)
                                    print(f"*** STATION {station_id} SYNCHRONIZED! ({len(synced_ids)}/{num_stations}) ***")
                                    print(f"synced_ids: {synced_ids}")
                                    print(f"Délka synced_ids: {len(synced_ids)}")
                            except:
                                pass
                except Exception as e:
                    print(f"Read error: {e}")
            
            time.sleep(0.1)
                

        
        # Send "READ" directive to Master to stop syncing
        print("Sending READ command to stop sync...")
        ser.write(b"READ\n")
        time.sleep(0.5)
        
        
        print("--- MASTER IS NOW READING CHIPS ---")
        print("(Press Ctrl+C to exit manager)")
        
        while True:
             if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"[MASTER] {line}")

    except Exception as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'ser' in locals():
            ser.close()

if __name__ == "__main__":
    main()
