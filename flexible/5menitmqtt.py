import paho.mqtt.client as mqtt
import zlib, json, base64, time
import numpy as np
import matplotlib.pyplot as plt
import pywt
from scipy.signal import butter, filtfilt, find_peaks
import psycopg2

# MQTT Configuration
app_id = "mayco"
api_key = "NNSXS.SOU4CMDQXBO6744VNIWBQRKKN5PMGQEY4ZL2SEA.MVNIBPC6A47TPR254IFIB67IHXLK4Y2TS4LPYIUWSLUULU26775A"
mqtt_host = "au1.cloud.thethings.network"
mqtt_port = 1883

uplink_topics = [
    "v3/mayco@ttn/devices/mayco-ekg/up",
    "v3/mayco@ttn/devices/mayco-ekg2/up",
    "v3/mayco@ttn/devices/mayco-ekg3/up",
]

FS = 125

# --- FUNGSI BARU UNTUK LOGGING KE DATABASE (DIPINDAHKAN KE ATAS) ---
def log_to_database(device_id, log_type, log_value):
    """
    Mencatat peristiwa ke tabel log_data di database.
    :param device_id: ID perangkat yang terkait dengan log.
    :param log_type: Tipe log (misal: "INFO", "WARNING", "ERROR", "DATA_RECEIVED").
    :param log_value: Deskripsi atau nilai log.
    """
    try:
        conn = psycopg2.connect(
            dbname="ecg_monitoring",
            user="admin",
            password="admin123",
            host="localhost",
            port="5432"
        )
        cur = conn.cursor()
        now = time.strftime("%Y-%m-%d %H:%M:%S") # Waktu saat ini
        cur.execute(
            "INSERT INTO log_data (timestamp, device_id, type, value) VALUES (%s, %s, %s, %s)",
            (now, device_id, log_type, log_value)
        )
        conn.commit() # Simpan perubahan ke database
        cur.close()
        conn.close()
        # print(f"[DB LOG] Logged: {log_type} - {log_value} for {device_id}") # Opsional: untuk debugging di konsol Python
    except Exception as e:
        print(f"[DB LOG ERROR] Gagal menulis log ke database: {e}")

# --- FUNGSI-FUNGSI PEMROSESAN SINYAL (TETAP DI SINI) ---
def bandpass_filter(signal, lowcut=0.5, highcut=40, fs=FS, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype="band")
    return filtfilt(b, a, signal)

def pan_tompkins_like(signal, fs=FS):
    diff = np.diff(signal, prepend=signal[0])
    squared = diff ** 2
    integrated = np.convolve(squared, np.ones(int(0.15 * fs)) / (0.15 * fs), mode="same")
    peaks, _ = find_peaks(integrated, distance=fs * 0.4, prominence=np.max(integrated) * 0.35)
    rr = np.diff(peaks) / fs
    hr = round(60 / np.mean(rr)) if len(rr) > 0 else None
    return hr

def sliding_window_hr(signal, fs=FS, window_sec=6, step_sec=2):
    window_size = int(window_sec * fs)
    step_size = int(step_sec * fs)
    result = []

    for start in range(0, len(signal) - window_size + 1, step_size):
        segment = signal[start:start + window_size]
        hr = pan_tompkins_like(segment, fs)
        if hr:
            # Koreksi menggunakan regresi linear
            corrected_hr = round(hr * 0.937 + 5.249)
            result.append(corrected_hr)

    return result

def decompress_dwt_per_level_zlib(compressed_parts, metadata, level=3):
    coeffs = []
    for i, comp in enumerate(compressed_parts):
        quantized = np.frombuffer(zlib.decompress(comp), dtype=np.uint8)
        assert len(quantized) == metadata[i]["length"]
        dequantized = quantized.astype(np.float32) * metadata[i]["q_step"] + metadata[i]["min_val"]
        coeffs.append(dequantized)
    return pywt.waverec(coeffs, "haar")

chunk_store = {}

# --- FUNGSI on_connect (TETAP DI SINI) ---
def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[MQTT] Connected with result code {reason_code}")
    for topic in uplink_topics:
        client.subscribe(topic)
        print(f"[INFO] Subscribed to {topic}")

# --- FUNGSI on_message (SEKARANG BISA MEMANGGIL log_to_database) ---
def on_message(client, userdata, msg):
    topic_parts = msg.topic.split("/")
    device_id = topic_parts[3]
    print(f"\n[Uplink] Data dari {device_id} diterima...")

    try:
        data = json.loads(msg.payload.decode())
        raw = base64.b64decode(data["uplink_message"]["frm_payload"])

        session_id = raw[0]
        chunk_index = (raw[1] << 8) | raw[2]
        total_chunks = (raw[3] << 8) | raw[4]
        payload = raw[5:]

        if session_id not in chunk_store:
            chunk_store[session_id] = {
                "chunks": {},
                "received": 0,
                "total": total_chunks,
                "timestamp": time.time()
            }

        store = chunk_store[session_id]
        if chunk_index not in store["chunks"]:
            store["chunks"][chunk_index] = payload
            store["received"] += 1
            print(f"[Chunk] ID={session_id} | Chunk {chunk_index+1}/{total_chunks} diterima")

        if store["received"] == store["total"]:
            print(f"[INFO] Semua chunk lengkap. Memproses data...")

            try:
                full_data = b''.join(store["chunks"][i] for i in range(total_chunks))
                print(f"[DEBUG] Total gabungan byte: {len(full_data)}")

                # ✅ Panggil fungsi untuk memproses dan simpan data ke database
                process_payload(full_data, device_id)

                del chunk_store[session_id]

            except Exception as e:
                print(f"[ERROR] Kesalahan saat proses payload: {e}")
                log_to_database(device_id, "ERROR", f"Payload processing error: {e}")
                if session_id in chunk_store:
                    del chunk_store[session_id]

    except Exception as e:
        print(f"[ERROR] Terjadi kesalahan saat memproses pesan: {e}")
        log_to_database(device_id, "ERROR", f"Message processing error: {e}")

# --- FUNGSI process_payload (SEKARANG BISA MEMANGGIL log_to_database) ---
def process_payload(payload, device_id):
    sep_marker = b"###META###"
    sep_idx = payload.find(sep_marker)
    if sep_idx == -1:
        # --- TAMBAHKAN LOG DI SINI: Separator tidak ditemukan ---
        log_to_database(device_id, "ERROR", "Metadata separator not found in payload.")
        raise ValueError("Metadata separator tidak ditemukan!")

    compressed = payload[:sep_idx]
    metadata_json = payload[sep_idx + len(sep_marker):].decode()
    metadata = json.loads(metadata_json)

    compressed_parts = []
    offset = 0
    for meta in metadata:
        part_len = meta["compressed_size"]
        compressed_parts.append(compressed[offset:offset + part_len])
        offset += part_len

    try:
        ecg_signal = decompress_dwt_per_level_zlib(compressed_parts, metadata)
        filtered = bandpass_filter(ecg_signal)
        hr_values = sliding_window_hr(filtered)
        # --- TAMBAHKAN LOG DI SINI: Data ECG berhasil diproses ---
        log_to_database(device_id, "INFO", "ECG signal processed successfully.")
    except Exception as e:
        print(f"[ERROR] Gagal memproses sinyal ECG: {e}")
        # --- TAMBAHKAN LOG DI SINI: Gagal memproses sinyal ECG ---
        log_to_database(device_id, "ERROR", f"Failed to process ECG signal: {e}")
        return # Hentikan eksekusi jika sinyal ECG gagal diproses

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = psycopg2.connect(
            dbname="ecg_monitoring",
            user="admin",
            password="admin123",
            host="localhost",
            port="5432"
        )
        cur = conn.cursor()
        cur.execute("SELECT id FROM patients WHERE device_id = %s", (device_id,))
        result = cur.fetchone()

        if result:
            patient_id = result[0]

            for hr in hr_values:
                cur.execute("INSERT INTO heart_rate (patient_id, bpm, timestamp) VALUES (%s, %s, %s)", (patient_id, hr, now))
            # --- TAMBAHKAN LOG DI SINI: HR disimpan ---
            log_to_database(device_id, "INFO", f"Heart Rate data saved for patient {patient_id}.")

            if hr_values:
                cur.execute("UPDATE patients SET heart_rate = %s, last_update = %s WHERE id = %s", (hr_values[-1], now, patient_id))
                # --- TAMBAHKAN LOG DI SINI: Pasien diupdate ---
                log_to_database(device_id, "INFO", f"Patient {patient_id} updated with latest HR: {hr_values[-1]} BPM.")

            for val in ecg_signal:
                cur.execute("INSERT INTO ecg_data (patient_id, value, timestamp) VALUES (%s, %s, %s)", (patient_id, float(val), now))
            # --- TAMBAHKAN LOG DI SINI: ECG disimpan ---
            log_to_database(device_id, "INFO", f"ECG raw data saved for patient {patient_id}.")

            conn.commit()
            print("[DB] Data HR & ECG berhasil disimpan ke database.")
            # --- TAMBAHKAN LOG DI SINI: Transaksi DB berhasil ---
            log_to_database(device_id, "SUCCESS", "All patient data (HR, ECG) successfully committed to database.")
        else:
            print(f"[DB WARNING] Device ID {device_id} tidak ditemukan di tabel patients.")
            # --- TAMBAHKAN LOG DI SINI: Device ID tidak ditemukan ---
            log_to_database(device_id, "WARNING", f"Device ID {device_id} not found in patients table. Data not saved.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")
        # --- TAMBAHKAN LOG DI SINI: Kesalahan database ---
        log_to_database(device_id, "ERROR", f"Database operation failed: {e}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(f"{app_id}@ttn", api_key)
client.on_connect = on_connect
client.on_message = on_message
client.connect(mqtt_host, mqtt_port)
client.loop_forever()