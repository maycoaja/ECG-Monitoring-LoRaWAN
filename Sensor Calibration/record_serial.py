import serial
import time
import csv

PORT = 'COM12'  # Ganti jika perlu
BAUD = 115200
DURATION_SEC = 60  # Lama pengambilan data

ser = serial.Serial(PORT, BAUD, timeout=1)
start = time.time()
filename = "ecg_raw_log2.csv"

print(f"[INFO] Merekam data ECG selama {DURATION_SEC} detik...")
last_print = 0
count = 0

with open(filename, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp_ms", "ecg_value"])
    while (time.time() - start) < DURATION_SEC:
        line = ser.readline().decode(errors='ignore').strip()
        if line.isdigit():
            now = time.time()
            timestamp = int((now - start) * 1000)
            writer.writerow([timestamp, int(line)])
            count += 1

            # Tampilkan progres setiap 1 detik
            if int(now - start) > last_print:
                last_print = int(now - start)
                print(f"[{last_print:02d}s] Sampel: {count}")

print(f"[INFO] Data disimpan ke {filename}")
ser.close()
