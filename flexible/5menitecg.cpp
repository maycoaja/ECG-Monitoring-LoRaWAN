#include <Arduino.h>
#include <lorawan.h>
#include <Preferences.h>
#include <algorithm>

// Konfigurasi Pin ECG
#define ECG_PIN 15
#define LO_PLUS_PIN 2
#define LO_MINUS_PIN 21

// Konfigurasi UART
#define UART_BAUDRATE 115200
#define UART_TX_PIN 17
#define UART_RX_PIN 16

// Konfigurasi Pengukuran
#define SAMPLE_RATE 125
#define DURATION_MS 300000UL                            //waktu dalam 1000/s
#define SAMPLE_INTERVAL_US (1000000UL / SAMPLE_RATE)  // Interval ms

// Konfigurasi LoRa
#define LORA_NSS 5
#define LORA_RST 4
#define LORA_DIO0 27
#define LORA_DIO1 14

const char *devAddr = "260D51A8";
const char *nwkSKey = "476985ACF7B07BBE3A27D61B8146907B";
const char *appSKey = "3EEB08AB4DCFDFE84D3CE79A2BA8712B";

const sRFM_pins RFM_pins = {
  .CS = LORA_NSS,
  .RST = LORA_RST,
  .DIO0 = LORA_DIO0,
  .DIO1 = LORA_DIO1,
};

Preferences prefs;
static uint32_t framecounter = 0;  // Inisialisasi dengan 0

// Variabel untuk pengukuran
unsigned long startMillis = 0;
bool isRecording = false;
bool waitingForCompression = false;
bool piReady = false;
bool shouldStartNewRecording = false;

void setup() {
  Serial.begin(115200);
  Serial1.begin(UART_BAUDRATE, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);

  pinMode(ECG_PIN, INPUT);
  pinMode(LO_PLUS_PIN, INPUT);
  pinMode(LO_MINUS_PIN, INPUT);
  delay(1000);

  if (!lora.init()) {
    Serial.println("LoRa Tidak Terdeteksi");
    while (1)
      ;
  }

  prefs.begin("lora", false);
  framecounter = prefs.getUInt("fcnt", 1);

  lora.setDeviceClass(CLASS_A);
  lora.setDataRate(SF10BW125);
  lora.setFramePortTx(1);
  lora.setChannel(MULTI);
  lora.setTxPower(1);
  lora.setNwkSKey(nwkSKey);
  lora.setAppSKey(appSKey);
  lora.setDevAddr(devAddr);
  lora.setFrameCounter(framecounter);
  delay(1000);
  lora.manualRX2();

  // Tunggu sampai Pi Zero siap (mengirim "READY")
  Serial.println("[INFO] Menunggu Pi Zero siap...");
  waitForPiReady();

  Serial.println("[INFO] Pi Zero siap. Memulai pengukuran ECG selama 5 menit...");
  startRecording();
}

void loop() {
  //Serial.printf("[STATE] recording=%d | waiting=%d | shouldStartNew=%d\n", isRecording, waitingForCompression, shouldStartNewRecording); //debug
  static unsigned long lastSampleTime = 0;
  unsigned long currentTime = millis();

  checkPiMessages();

  // Proses permintaan rekaman ulang di luar blok rekaman
  if (shouldStartNewRecording && !isRecording && !waitingForCompression) {
    waitForPiReady();         // Tunggu Pi siap dulu
    startRecording();         // Baru mulai rekaman
    shouldStartNewRecording = false;
    return;
  }

  // Jangan lanjut kalau sedang tunggu kompresi
  if (waitingForCompression) return;

  // 🚩 Rekaman aktif
  if (isRecording) {
    bool leadOff = digitalRead(LO_PLUS_PIN) || digitalRead(LO_MINUS_PIN);
    if (leadOff) {
      Serial.println("[WARN] Lead-off terdeteksi! Menghentikan rekaman.");
      isRecording = false;
      waitingForCompression = false;
      shouldStartNewRecording = true;
      return;
    }

    unsigned long nowMicros = micros();
    if (nowMicros - lastSampleTime >= SAMPLE_INTERVAL_US) {
      lastSampleTime = nowMicros;
      int sample = analogRead(ECG_PIN);
      Serial1.println(sample);
    }

    if (currentTime - startMillis >= DURATION_MS) {
      Serial1.println("[END]");
      Serial.println("[INFO] Akhir rekaman. Menunggu data kompresi...");
      isRecording = false;
      waitingForCompression = true;
    }
  }
}


void waitForPiReady() {
  unsigned long startTime = millis();
  bool requestSent = false;

  while (millis() - startTime < 30000) {
    // Kirim permintaan setiap 2 detik
    if (!requestSent || (millis() - startTime) % 2000 < 50) {
      Serial1.println("REQUEST_READY");
      requestSent = true;
      Serial.println("[INFO] Meminta konfirmasi kesiapan Pi Zero...");
    }

    // Cek respon
    if (Serial1.available()) {
      String response = Serial1.readStringUntil('\n');
      response.trim();

      if (response == "READY") {
        Serial.println("[INFO] Pi Zero siap menerima data");
        piReady = true;
        return;
      }
    }
    delay(10);
  }

  // Fallback jika timeout
  Serial.println("[WARN] Timeout, asumsikan Pi Zero siap");
  piReady = true;
}

void checkPiMessages() {
  static String message = "";

  while (Serial1.available()) {
    char c = Serial1.read();
    if (c == '\n') {
      processPiMessage(message);
      message = "";
    } else {
      message += c;
    }
  }
}

void processPiMessage(String msg) {
  msg.trim();

  if (msg == "READY") {
    piReady = true;
    Serial.println("[INFO] Pi Zero siap menerima data");
  } else if (msg.startsWith("[COMPRESSED];")) {
    int hexIdx = msg.indexOf("hex=");
    if (hexIdx >= 0) {
      String hexStr = msg.substring(hexIdx + 4);
      hexStr.trim();
      handleCompressedData(hexStr);
    }
  }
}

void startRecording() {
  // Tunggu sampai Pi Zero siap
  if (!piReady) {
    Serial.println("[WARN] Pi Zero belum siap, menunda rekaman...");
    return;
  }

  // Kirim perintah [START] dan sample rate
  Serial1.println("[START]");
  Serial1.println(SAMPLE_RATE);
  startMillis = millis();
  isRecording = true;
  waitingForCompression = false;
  Serial.println("[INFO] Rekaman dimulai...");
  Serial.printf("[DEBUG] Rekaman dimulai ulang @ %lu ms\n", millis());
}

void handleCompressedData(String hexStr) {
  // Konversi hex string ke byte array
  int byteLen = hexStr.length() / 2;
  byte *payload = (byte *)malloc(byteLen);  // Pastikan payload dideklarasikan dengan benar
  for (int i = 0; i < byteLen; i++) {
    char buf[3] = { hexStr[i * 2], hexStr[i * 2 + 1], '\0' };
    payload[i] = (byte)strtol(buf, NULL, 16);
  }

  Serial.printf("[INFO] Data kompresi diterima (%d byte). Mengirim via LoRa...\n", byteLen);
  sendLoRaChunked(payload, byteLen);
  free(payload);  // Jangan lupa untuk membebaskan memori

  waitingForCompression = false;
  delay(3000);  // Beri jeda sebelum sesi berikutnya

  piReady = false;
  shouldStartNewRecording = true;  // Jangan langsung rekam, beri waktu Pi dulu
}

void sendLoRaChunked(byte *data, int length) {
  Serial.println("[INFO] Mengirim data via LoRa (chunked)...");

  const int chunkSize = 45;
  byte session_id = (byte)(millis() & 0xFF);  // bisa juga pakai random(0,255)
  int totalChunks = (length + chunkSize - 1) / chunkSize;

  if (totalChunks > 65535) {
    Serial.println("[ERROR] Total chunks terlalu banyak (>65535)!");
    return;
  }

  for (int i = 0; i < totalChunks; i++) {
    byte chunk[5 + chunkSize] = { 0 };
    chunk[0] = session_id;

    // Simpan chunk_id (i) ke 2 byte
    chunk[1] = (i >> 8) & 0xFF;
    chunk[2] = i & 0xFF;

    // Simpan totalChunks ke 2 byte
    chunk[3] = (totalChunks >> 8) & 0xFF;
    chunk[4] = totalChunks & 0xFF;

    int copyLen = min(chunkSize, length - i * chunkSize);
    memcpy(&chunk[5], &data[i * chunkSize], copyLen);

    lora.setFrameCounter(framecounter++);
    prefs.putUInt("fcnt", framecounter);
    lora.sendUplink((char *)chunk, 5 + copyLen, 1);
    lora.update();

    Serial.printf("[INFO] Chunk %d/%d dikirim (%d bytes)\n", i + 1, totalChunks, 5 + copyLen);
    delay(250);
  }
}