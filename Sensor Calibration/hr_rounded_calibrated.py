import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
import math

# ==== KONFIGURASI ====
FS = 125
WINDOW_SEC = 6
STEP_SEC = 2
LOWCUT = 0.5
HIGHCUT = 40
INPUT_FILE = "data1.csv"
OUTPUT_FILE = "data1hrx.csv"

# ==== PARAMETER REGRESI ====
SLOPE = 0.937
INTERCEPT = 5.249


# ==== FUNGSI ROUND HALF UP ====
def round_half_up(n, decimals=0):
    multiplier = 10**decimals
    return math.floor(n * multiplier + 0.5) / multiplier


# ==== FILTER BANDPASS ====
def bandpass_filter(signal, fs=FS, lowcut=LOWCUT, highcut=HIGHCUT, order=3):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = min(highcut / nyq, 0.99)
    b, a = butter(order, [low, high], btype="band")
    return filtfilt(b, a, signal)


# ==== DETEKSI HR ala Pan-Tompkins ====
def pan_tompkins_like(signal, fs=FS):
    diff = np.diff(signal, prepend=signal[0])
    squared = diff**2
    ma_window = int(0.15 * fs)
    integrated = np.convolve(squared, np.ones(ma_window) / ma_window, mode="same")
    peaks, _ = find_peaks(
        integrated, distance=fs * 0.4, prominence=np.max(integrated) * 0.35
    )
    rr = np.diff(peaks) / fs
    hr = round_half_up(60 / np.mean(rr)) if len(rr) > 0 else None
    return hr


# ==== BACA DATA ====
df = pd.read_csv(INPUT_FILE)
df = df.dropna()

# Tambahkan timestamp jika tidak ada
if "timestamp_ms" not in df.columns:
    df["timestamp_ms"] = np.arange(0, len(df)) * (1000 // FS)

# Normalisasi timestamp ke detik
df["timestamp_s"] = df["timestamp_ms"] / 1000.0
df["index"] = (df["timestamp_s"] * FS).astype(int)

# Interpolasi agar data genap
full = pd.DataFrame({"index": np.arange(0, df["index"].max() + 1)})
merged = full.merge(df[["index", "ecg_value"]], on="index", how="left")
merged["ecg_value"] = merged["ecg_value"].interpolate().bfill()

# ==== PROSES HR WINDOW ====
data = merged["ecg_value"].values
window_size = WINDOW_SEC * FS
step_size = STEP_SEC * FS

rows = []
for start in range(0, len(data) - window_size + 1, step_size):
    window = data[start : start + window_size]
    filtered = bandpass_filter(window)
    hr = pan_tompkins_like(filtered)
    hr_corrected = round_half_up((hr - INTERCEPT) / SLOPE) if hr is not None else None
    rows.append(
        {
            "window_start_s": int(round_half_up(start / FS)),
            "HR_ECG": int(hr) if hr is not None else None,
            "HR_ECG_Corrected": int(hr_corrected) if hr_corrected is not None else None,
            "HR_PulseOx": "",
        }
    )


df_out = pd.DataFrame(rows)
df_out.to_csv(OUTPUT_FILE, index=False)
print(f"[INFO] Analisis selesai. Hasil disimpan ke {OUTPUT_FILE}")
