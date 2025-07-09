import paho.mqtt.client as mqtt
import zlib, json, base64, time
import numpy as np
import matplotlib.pyplot as plt
import pywt
from scipy.signal import butter, filtfilt, find_peaks
import psycopg2

# MQTT Configuration
app_id = "mayco"
api_key = "NNSXS.xxxx"
mqtt_host = "au1.cloud.thethings.network"
mqtt_port = 1883

uplink_topics = [
    "v3/mayco@ttn/devices/mayco-ekg/up",
    "v3/mayco@ttn/devices/mayco-ekg2/up",
    "v3/mayco@ttn/devices/mayco-ekg3/up",
]

FS = 125

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

def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[MQTT] Connected with result code {reason_code}")
    for topic in uplink_topics:
        client.subscribe(topic)
        print(f"[INFO] Subscribed to {topic}")

def on_message(client, userdata, msg):
    topic_parts = msg.topic.split("/")
    device_id = topic_parts[3]
    print(f"\\n[Uplink] Data dari {device_id} diterima...")

    data = json.loads(msg.payload.decode())
    raw = base64.b64decode(data["uplink_message"]["frm_payload"])

    session_id = raw[0]
    chunk_id = raw[1]
    total_chunks = raw[2]
    chunk_data = raw[3:]

    key = (device_id, session_id)
    if key not in chunk_store:
        chunk_store[key] = {"chunks": {}, "total": total_chunks, "start_time": time.time()}

    chunk_store[key]["chunks"][chunk_id] = chunk_data
    print(f" - Chunk {chunk_id + 1}/{total_chunks}, Size {len(chunk_data)} bytes")

    received_chunks = chunk_store[key]["chunks"]
    if len(received_chunks) == total_chunks:
        try:
            full_payload = b"".join(received_chunks[i] for i in range(total_chunks))
            del chunk_store[key]
            process_payload(full_payload, device_id)
        except Exception as e:
            print(f"[ERROR] Gagal assembling payload: {e}")
            del chunk_store[key]

def process_payload(payload, device_id):
    sep_marker = b"###META###"
    sep_idx = payload.find(sep_marker)
    if sep_idx == -1:
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

    ecg_signal = decompress_dwt_per_level_zlib(compressed_parts, metadata)
    filtered = bandpass_filter(ecg_signal)
    hr_values = sliding_window_hr(filtered)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = psycopg2.connect(
            dbname="ecg_monitoring",
            user="admin",
            password="xxx",
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

            if hr_values:
                cur.execute("UPDATE patients SET heart_rate = %s, last_update = %s WHERE id = %s", (hr_values[-1], now, patient_id))

            for val in ecg_signal:
                cur.execute("INSERT INTO ecg_data (patient_id, value, timestamp) VALUES (%s, %s, %s)", (patient_id, float(val), now))

            conn.commit()
            print("[DB] Data HR & ECG berhasil disimpan ke database.")
        else:
            print(f"[DB WARNING] Device ID {device_id} tidak ditemukan di tabel patients.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(f"{app_id}@ttn", api_key)
client.on_connect = on_connect
client.on_message = on_message
client.connect(mqtt_host, mqtt_port)
client.loop_forever()
