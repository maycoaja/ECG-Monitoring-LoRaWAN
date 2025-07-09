import serial
import numpy as np
import pywt
import zlib
import time
import json
from scipy.signal import butter, filtfilt

# --- Serial Setup ---
SERIAL_PORT = "/dev/serial0"
BAUDRATE = 115200
ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)

# --- Bandpass Filter ---
def bandpass_filter(data, lowcut=0.5, highcut=40.0, fs=125.0, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut/nyq, highcut/nyq], btype='band')
    return filtfilt(b, a, data)

# --- PRD & CC ---
def calculate_prd(original, reconstructed):
    return 100 * np.sqrt(np.sum((original - reconstructed) ** 2) / np.sum(original ** 2))

def calculate_cc(original, reconstructed):
    return np.corrcoef(original, reconstructed)[0, 1]

# --- Kompresi DWT + Quant + zlib ---
def compress_dwt_per_level_zlib(signal, level=3, q_bits=6):
    coeffs = pywt.wavedec(signal, 'haar', level=level)
    compressed_parts = []
    metadata = {'lengths': [], 'min_vals': [], 'q_steps': []}

    for coeff in coeffs:
        min_val = np.min(coeff)
        max_val = np.max(coeff)
        q_step = (max_val - min_val) / (2 ** q_bits) if max_val != min_val else 1.0
        quantized = np.round((coeff - min_val) / q_step).astype(np.uint8)
        compressed = zlib.compress(quantized.tobytes())
        
        compressed_parts.append(compressed)
        metadata['lengths'].append(len(quantized))
        metadata['min_vals'].append(float(min_val))
        metadata['q_steps'].append(float(q_step))

    return compressed_parts, metadata

# --- Dekompresi DWT ---
def decompress_dwt_per_level_zlib(compressed_parts, metadata, level=3):
    coeffs = []
    for i, compressed in enumerate(compressed_parts):
        quantized = np.frombuffer(zlib.decompress(compressed), dtype=np.uint8)
        assert len(quantized) == metadata['lengths'][i], "Panjang tidak sesuai"

        dequantized = quantized.astype(np.float32) * metadata['q_steps'][i] + metadata['min_vals'][i]
        coeffs.append(dequantized)

    reconstructed = pywt.waverec(coeffs, 'haar')
    return reconstructed

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

    # --- Filter dan Kompresi ---
    ecg_array = np.array(ecgs, dtype=np.float32)
    filtered = bandpass_filter(ecg_array)

    print("[INFO] Kompresi menggunakan DWT Level 3 + Quant + zlib...")
    start_time = time.time()

    compressed_parts, metadata = compress_dwt_per_level_zlib(filtered, level=3, q_bits=6)
    compressed = b''.join(compressed_parts)

    end_time = time.time()

    # --- Gabungkan compressed + marker + metadata ---
    meta_json = json.dumps([
        {"compressed_size": len(comp),
         "length": meta_len,
         "min_val": minv,
         "q_step": qstep}
        for comp, meta_len, minv, qstep in zip(compressed_parts, metadata['lengths'], metadata['min_vals'], metadata['q_steps'])
    ])

    marker = b'###META###'
    full_payload = compressed + marker + meta_json.encode()

    # --- Dekompresi untuk Evaluasi ---
    reconstructed = decompress_dwt_per_level_zlib(compressed_parts, metadata, level=3)[:len(filtered)]

    prd = calculate_prd(filtered, reconstructed)
    cc = calculate_cc(filtered, reconstructed)

    # --- Statistik Kompresi ---
    original_size = len(filtered) * 2  # 2 bytes per sampel asumsinya int16
    compressed_size = len(compressed)

    print("\n=== PERFORMA KOMRESI DWT + Quant + zlib ===")
    print(f"Jumlah Sampel     : {len(filtered)}")
    print(f"Original Size     : {original_size} bytes")
    print(f"Compressed Size   : {compressed_size} bytes")
    print(f"Compression Ratio : {round(original_size / compressed_size, 2)}x")
    print(f"PRD               : {round(prd, 2)}%")
    print(f"CC (Correlation)  : {round(cc, 4)}")
    print(f"Durasi Kompresi   : {round(end_time - start_time, 3)} detik")

    # --- Kirim ke ESP32 ---
    hex_str = full_payload.hex()
    header = f"[COMPRESSED];hex={hex_str}\n"
    ser.write(header.encode())
    ser.flush()
    print("[INFO] Payload gabungan + metadata dikirim ke ESP32.\n")