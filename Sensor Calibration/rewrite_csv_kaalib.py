import pandas as pd

# BACA DUA FILE
df_awal = pd.read_csv("data1hr.csv")           # File yang sudah ada HR_PulseOx
df_calib = pd.read_csv("data1hrx.csv")    # File hasil kalibrasi, mau diisi ulang HR_PulseOx

# GABUNG BERDASARKAN window_start_s
df_calib = df_calib.drop(columns=["HR_PulseOx"], errors="ignore")  # Buang kolom HR_PulseOx lama kalo ada
df_merge = pd.merge(df_calib, df_awal[["window_start_s", "HR_PulseOx"]], on="window_start_s", how="left")

# SIMPAN ULANG FILE
df_merge.to_csv("data1hrx.csv", index=False)
print("[INFO] File berhasil diupdate, kolom HR_PulseOx sudah digabung.")
