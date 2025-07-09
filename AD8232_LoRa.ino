#include <Arduino.h>
#include <lorawan.h>
#include <Preferences.h>
#include <algorithm>

#define ECG_PIN         33
#define LO_PLUS_PIN     35
#define LO_MINUS_PIN    32

#define UART_BAUDRATE   115200
#define UART_TX_PIN     17
#define UART_RX_PIN     16

#define SAMPLE_RATE     125
#define DURATION_MS     60000UL
#define SAMPLES_TOTAL   (SAMPLE_RATE * DURATION_MS / 1000UL)

#define LORA_NSS   5
#define LORA_RST   4
#define LORA_DIO0  27
#define LORA_DIO1  14

const char *devAddr = "xxx";
const char *nwkSKey = "xxx";
const char *appSKey = "xxx";

const sRFM_pins RFM_pins = {
  .CS = LORA_NSS,
  .RST = LORA_RST,
  .DIO0 = LORA_DIO0,
  .DIO1 = LORA_DIO1,
};

Preferences prefs;
static uint32_t framecounter = framecounter;

int ecgBuffer[SAMPLES_TOTAL];
int sampleIndex;
unsigned long startMillis = 0;
bool dataReadyToSend = false;

void setup() {
  Serial.begin(115200);
  Serial1.begin(UART_BAUDRATE, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);

  pinMode(ECG_PIN, INPUT);
  pinMode(LO_PLUS_PIN, INPUT);
  pinMode(LO_MINUS_PIN, INPUT);
  delay(1000);

  if (!lora.init()) {
    Serial.println("LoRa Tidak Terdeteksi");
    while (1);
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

  Serial.println("[INFO] Mulai Pengukuran ECG selama 60 detik...");
  startMillis = millis();
}

void loop() {
  if (dataReadyToSend) {
    sendBufferToPi();
    waitForCompressedFromPi();
    resetForNextCycle();
    return;
  }

  bool leadOff = digitalRead(LO_PLUS_PIN) || digitalRead(LO_MINUS_PIN);
  if (leadOff) return;

  static unsigned long lastSampleMicros = 0;
  unsigned long nowMicros = micros();
  if (nowMicros - lastSampleMicros >= 1000000UL / SAMPLE_RATE) {
    lastSampleMicros = nowMicros;
    if (sampleIndex < SAMPLES_TOTAL) {
      ecgBuffer[sampleIndex++] = analogRead(ECG_PIN);
    }
  }

  if ((millis() - startMillis >= DURATION_MS) && sampleIndex >= SAMPLES_TOTAL) {
    dataReadyToSend = true;
  }
}

void resetForNextCycle() {
  sampleIndex = 0;
  dataReadyToSend = false;
  startMillis = millis();
}

void sendBufferToPi() {
  Serial.println("[INFO] Kirim data ECG ke RasPi0...");
  Serial1.println("[BATCH_START]");
  for (int i = 0; i < SAMPLES_TOTAL; i++) {
    Serial1.println(ecgBuffer[i]);
  }
  Serial1.println("[BATCH_END]");
}

void waitForCompressedFromPi() {
  String line = "", hexStr = "";
  bool found = false;
  unsigned long start = millis();

  Serial.println("[INFO] Menunggu hasil kompresi dari RasPi...");

  while (millis() - start < 20000) { // tunggu maksimal 20 detik
    while (Serial1.available()) {
      char c = Serial1.read();
      if (c == '\n' || c == '\r') {
        if (line.startsWith("[COMPRESSED];")) {
          int hexIdx = line.indexOf("hex=");
          if (hexIdx >= 0) {
            hexStr = line.substring(hexIdx + 4);
            hexStr.trim();
            found = true;
            break;
          }
        }
        line = "";
      } else {
        line += c;
      }
    }

    if (found) break;
    delay(5);
  }

  if (!found) {
    Serial.println("[WARN] Tidak ada respon dari RasPi (timeout)");
    return;
  }

  // Convert hex string ke byte array
  int byteLen = hexStr.length() / 2;
  byte* payload = (byte*)malloc(byteLen);
  for (int i = 0; i < byteLen; i++) {
    char buf[3] = {hexStr[i * 2], hexStr[i * 2 + 1], 0};
    payload[i] = (byte)strtol(buf, NULL, 16);
  }

  Serial.printf("[INFO] Kompresi diterima: %d byte, kirim ke LoRa...\n", byteLen);
  sendLoRaChunked(payload, byteLen); // pastikan fungsi ini sudah aman chunking
  free(payload);
}


void sendLoRaChunked(byte* data, int length) {
  Serial.println("[INFO] Kirim via LoRa...");
  const int chunkSize = 45;
  byte session_id = random(0, 255);
  int totalChunks = (length + chunkSize - 1) / chunkSize;

  for (int i = 0; i < totalChunks; i++) {
    byte chunk[3 + chunkSize] = {0};
    chunk[0] = session_id;
    chunk[1] = i;
    chunk[2] = totalChunks;

    int copyLen = min(chunkSize, length - i * chunkSize);
    memcpy(&chunk[3], &data[i * chunkSize], copyLen);

    lora.setFrameCounter(framecounter++);
    prefs.putUInt("fcnt", framecounter);
    lora.sendUplink((char*)chunk, 3 + copyLen, 1);
    lora.update();

    Serial.printf("[INFO] Chunk %d/%d dikirim (%d bytes)\n", i + 1, totalChunks, 3 + copyLen);
    delay(250);
  }
}
