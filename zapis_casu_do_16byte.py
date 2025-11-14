import sys


def decimal_to_full_16_bytes():
    # --- INPUT DATA ---
    # šest časů v sekundách, max 16bitů tzn. 65535.

    NUMBERS_TO_ENCODE=[]
    opakovani=1
    pocet_cisel=int(input("kolik čísel budete zadávat?: "))
    for i in range(pocet_cisel):
        NUMBERS_TO_ENCODE.append(int(input(f"zadejte {opakovani}. čas: ")))
        opakovani+=1


    NUM_BYTES_PER_INTEGER = 2  # 2 byty neboli 16 bitů
    TARGET_TOTAL_LENGTH = 16   # musí to být full 16 bytes pro zápis do bloku na rfid čipu
    BYTE_ORDER = 'big'         # Big-endian: Most significant byte comes first (easier to read)

    def serialize_to_fixed_bytes(numbers: list[int], target_length: int) -> bytes:
        """
        Converts a list of integers into a fixed-length byte string using padding.

        :param numbers: The list of integers to encode.
        :param target_length: The required final length of the byte string.
        :return: The final byte string, padded to the target_length.
        """
        serialized_data = b''

        # 1. Convert each integer to 2 fixed bytes (16-bit)
        for num in numbers:
            # Check if the number fits in 16 bits (0 to 65535)
            if not 0 <= num < 2**16:
                # sys.exit() is used instead of print/raise to stop execution safely in this environment
                sys.exit(f"Error: Number {num} exceeds the 16-bit limit (65535) and cannot be stored in 2 bytes.")

            # Use int.to_bytes() to serialize the integer
            serialized_data += num.to_bytes(NUM_BYTES_PER_INTEGER, byteorder=BYTE_ORDER)

        # 2. Calculate and apply padding
        current_length = len(serialized_data)
        padding_needed = target_length - current_length

        if padding_needed < 0:
            sys.exit(f"Error: Serialized data length ({current_length} bytes) exceeds the target length ({target_length} bytes).")

        # Pad with null bytes (\x00)
        padding = b'\x00' * padding_needed
        final_bytes = serialized_data + padding

        return final_bytes

    # --- EXECUTION ---
    DATA_TO_WRITE = serialize_to_fixed_bytes(NUMBERS_TO_ENCODE, TARGET_TOTAL_LENGTH)

    # --- OUTPUT AND VERIFICATION ---
    print("--- Result Summary ---")
    print(f"Original Numbers: {NUMBERS_TO_ENCODE}")
    print(f"Target Size: {TARGET_TOTAL_LENGTH} bytes")
    print(f"Final Size: {len(DATA_TO_WRITE)} bytes")
    print("-" * 20)

    # Display the resulting byte string in the requested format:
    print(f'#DATA_TO_WRITE = {repr(DATA_TO_WRITE)}')
    print("-" * 20)

    # Optional: Display content breakdown
    print("\n--- Content Breakdown (Big-Endian) ---")
    print("| Hex | Dec | Bytes |")
    print("|:---:|:---:|:---:|")

    for i in range(0, 12, 2):
        # Reconstruct the integer from the 2-byte block for display
        hex_value = DATA_TO_WRITE[i:i+2].hex().upper()
        dec_value = int.from_bytes(DATA_TO_WRITE[i:i+2], byteorder=BYTE_ORDER)
        print(f"| {hex_value} | {dec_value} | \\x{hex_value[:2]}\\x{hex_value[2:]} |")

    print("| Padding | N/A | \\x00\\x00\\x00\\x00 |")
    print("-" * 20)

    return(DATA_TO_WRITE)


def full_16_bytes_to_decimal(byte_string):

    import struct


    # --- Configuration ---
    # 2 bytes per number (H means unsigned short integer, which is 2 bytes)
    # > means Big-Endian byte order
    # The total format string is eight 'H' codes preceded by '>'
    FORMAT_STRING = '>HHHHHHHH' 

    # --- Decoding Process ---

    # 1. Check if the byte string length matches the expected format length
    expected_length = struct.calcsize(FORMAT_STRING)
    if len(byte_string) != expected_length:
        print(f"Error: Byte string length ({len(byte_string)} bytes) does not match the expected length for the format ({expected_length} bytes).")
    else:
        # 2. Use struct.unpack to decode the entire byte string in one go
        # The result is a tuple of the decoded decimal numbers
        decoded_numbers = struct.unpack(FORMAT_STRING, byte_string)

        # 3. Print the results
        print(f"Original Byte String: {byte_string.hex()}")
        print(f"Format String Used: '{FORMAT_STRING}' (Big-Endian, 8 x 2-byte unsigned integers)")
        print("-" * 35)
        print("Decoded Decimal Values:")
        
        # Print each number for clarity
        for i, number in enumerate(decoded_numbers):
            # Calculate the start and end indices for the original bytes of this number
            start_byte = i * 2
            end_byte = (i + 1) * 2
            
            # Get the original 2 bytes in hex format
            original_bytes_hex = byte_string[start_byte:end_byte].hex().upper()
            
            print(f"  [{original_bytes_hex}] -> {number}")
        
        print("-" * 35)
        print(f"Final List: {list(decoded_numbers)}")





full_16_bytes_to_decimal(decimal_to_full_16_bytes())

#byte_string = b'\x01,\x16B\x0c\xc1\x11\\\x04\xb0\x02X\x00\x00\x00\x00'