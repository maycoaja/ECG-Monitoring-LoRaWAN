import serial
import csv
import time

PORT = "COM12"
BAUD = 115200
FS = 125
DURATION_SEC = 300
FILENAME = "ecg_raw_125hz_wawan2.csv"

ser = serial.Serial(PORT, BAUD, timeout=1)
start = time.time()
last_print = 0
count = 0

print(f"[INFO] Mulai merekam selama {DURATION_SEC} detik...")

with open(FILENAME, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ecg_value"])

    while (time.time() - start) < DURATION_SEC:
        line = ser.readline().decode(errors="ignore").strip()
        if line.isdigit():
            writer.writerow([int(line)])
            count += 1

        now_sec = int(time.time() - start)
        if now_sec > last_print:
            last_print = now_sec
            print(f"[{now_sec:02d}s] Sampel: {count}")

ser.close()
print(f"[INFO] Selesai. Total: {count} sampel. Data disimpan di {FILENAME}")
