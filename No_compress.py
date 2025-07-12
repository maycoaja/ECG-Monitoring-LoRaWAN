import serial
import numpy as np
import time
from scipy.signal import butter, filtfilt

# --- Serial Setup ---
SERIAL_PORT = "/dev/serial0"
BAUDRATE = 115200
ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)

# --- Bandpass Filter ---
def bandpass_filter(data, lowcut=0.5, highcut=40.0, fs=125.0, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return filtfilt(b, a, data)

# --- Loop Utama ---
while True:
    ecgs = []
    inside_batch = False
    print("\n[INFO] Menunggu data ECG dari ESP32...")

    while True:
        line = ser.readline().decode(errors='ignore').strip()

        if line == "[BATCH_START]":
            ecgs = []
            inside_batch = True
            continue
        elif line == "[BATCH_END]":
            inside_batch = False
            if len(ecgs) > 0:
                print(f"[INFO] Data ECG diterima: {len(ecgs)} sampel")
                break
            else:
                print("[WARN] Tidak ada data diterima.")
                continue

        if inside_batch:
            try:
                val = int(line)
                ecgs.append(val)
            except:
                continue

    # --- Filter (tanpa kompresi) ---
    ecg_array = np.array(ecgs, dtype=np.float32)
    filtered = bandpass_filter(ecg_array)

    # --- Konversi ke int16 dan encode sebagai hex string ---
    filtered_int16 = np.round(filtered).astype(np.int16)
    hex_payload = filtered_int16.tobytes().hex()

    # --- Format sesuai ekspektasi ESP32 ---
    header = f"[COMPRESSED];hex={hex_payload}\n"
    ser.write(header.encode())
    ser.flush()

    print(f"[INFO] Payload ECG (filtered, no compress) dikirim ke ESP32. Size: {len(filtered_int16)*2} bytes\n")
