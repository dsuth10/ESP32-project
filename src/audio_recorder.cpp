#include "audio_recorder.h"
#include "es8311.h"
#include "driver/i2s.h"

#define I2S_PORT         I2S_NUM_0
#define PIN_I2S_MCLK     4
#define PIN_I2S_BCLK     5
#define PIN_I2S_WS       7
#define PIN_I2S_DOUT     8  // ESP32 I2S DOUT (Speaker / DAC DSDIN)
#define PIN_I2S_DIN      6  // ESP32 I2S DIN (Microphone / ADC ASDOUT)
#define PIN_PA_ENABLE    1

AudioRecorder recorder;

AudioRecorder::AudioRecorder()
    : _psramBuffer(nullptr),
      _pcmBytesRecorded(0),
      _totalWavBytes(0),
      _isRecording(false),
      _recordStartTime(0),
      _lastRecordDurationMs(0) {}

bool AudioRecorder::begin() {
    // 1. Ensure Audio Power Amplifier (FM8002, active-LOW) is shut down / muted
    pinMode(PIN_PA_ENABLE, OUTPUT);
    digitalWrite(PIN_PA_ENABLE, HIGH);

    // 2. Allocate PSRAM Audio Buffer
    _psramBuffer = (uint8_t*)ps_malloc(MAX_AUDIO_BUFFER_SIZE);
    if (!_psramBuffer) {
        Serial.println("[Recorder] Failed to allocate audio buffer in PSRAM!");
        return false;
    }
    Serial.printf("[Recorder] Allocated %u bytes in PSRAM for audio recording\n", (unsigned int)MAX_AUDIO_BUFFER_SIZE);

    // 3. Configure I2S Driver (IDF 4.4 standard API)
    // Master RX+TX mode (TX ensures master clock MCLK is continuously generated on GPIO 4)
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_TX),
        .sample_rate = AUDIO_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 512,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0,
        .mclk_multiple = I2S_MCLK_MULTIPLE_256,
        .bits_per_chan = I2S_BITS_PER_CHAN_16BIT
    };

    i2s_pin_config_t pin_config = {
        .mck_io_num = PIN_I2S_MCLK,
        .bck_io_num = PIN_I2S_BCLK,
        .ws_io_num = PIN_I2S_WS,
        .data_out_num = PIN_I2S_DOUT,
        .data_in_num = PIN_I2S_DIN
    };

    esp_err_t err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
    if (err != ESP_OK) {
        Serial.printf("[Recorder] I2S driver install failed: 0x%x\n", err);
        return false;
    }

    err = i2s_set_pin(I2S_PORT, &pin_config);
    if (err != ESP_OK) {
        Serial.printf("[Recorder] I2S set pin failed: 0x%x\n", err);
        return false;
    }

    // 4. Initialize ES8311 Codec (over Wire I2C)
    if (es8311_codec_init() != ESP_OK) {
        Serial.println("[Recorder] ES8311 init failed!");
        return false;
    }

    Serial.println("[Recorder] Audio system initialized successfully");
    return true;
}

bool AudioRecorder::startRecording() {
    if (!_psramBuffer) return false;

    // Actively drain any pre-existing queued RX DMA samples before recording
    uint8_t drainBuf[512];
    size_t drainedBytes = 0;
    do {
        drainedBytes = 0;
        i2s_read(I2S_PORT, (void*)drainBuf, sizeof(drainBuf), &drainedBytes, 0);
    } while (drainedBytes > 0);

    _pcmBytesRecorded = 0;
    _totalWavBytes = 0;
    _isRecording = true;
    _recordStartTime = millis();
    _maxLeftPeak = 0;
    _maxRightPeak = 0;

    _leftStats.reset();
    _rightStats.reset();
    _monoStats.reset();
    _previewCount = 0;

    Serial.println("[Recorder] >>> START RECORDING <<<");
    return true;
}

void AudioRecorder::update() {
    if (!_isRecording) return;

    // Check max duration safety cutoff
    if (millis() - _recordStartTime >= (MAX_RECORD_SECONDS * 1000)) {
        Serial.println("[Recorder] Max record duration reached");
        stopRecording();
        return;
    }

    // Read available I2S stereo samples
    const size_t CHUNK_SAMPLES = 256;
    int16_t stereoBuf[CHUNK_SAMPLES * 2];
    size_t bytesRead = 0;

    esp_err_t ret = i2s_read(I2S_PORT, (void*)stereoBuf, sizeof(stereoBuf), &bytesRead, 10);
    if (ret == ESP_OK && bytesRead > 0) {
        size_t samplesRead = bytesRead / (sizeof(int16_t) * 2);
        size_t maxPcmBytes = MAX_AUDIO_BUFFER_SIZE - 44;

        int16_t* pcmDest = (int16_t*)(_psramBuffer + 44 + _pcmBytesRecorded);
        for (size_t i = 0; i < samplesRead; i++) {
            if (_pcmBytesRecorded + sizeof(int16_t) > maxPcmBytes) {
                stopRecording();
                return;
            }
            int16_t left = stereoBuf[i * 2];
            int16_t right = stereoBuf[i * 2 + 1];

            // 1. Left channel statistics (64-bit accumulators prevent overflow)
            _leftStats.count++;
            if (left < _leftStats.minVal) _leftStats.minVal = left;
            if (left > _leftStats.maxVal) _leftStats.maxVal = left;
            _leftStats.sum += left;
            _leftStats.sumSq += (uint64_t)((int32_t)left * (int32_t)left);
            if (left != 0) _leftStats.nonZeroCount++;
            if (left <= -32767 || left >= 32767) _leftStats.clipCount++;

            // 2. Right channel statistics
            _rightStats.count++;
            if (right < _rightStats.minVal) _rightStats.minVal = right;
            if (right > _rightStats.maxVal) _rightStats.maxVal = right;
            _rightStats.sum += right;
            _rightStats.sumSq += (uint64_t)((int32_t)right * (int32_t)right);
            if (right != 0) _rightStats.nonZeroCount++;
            if (right <= -32767 || right >= 32767) _rightStats.clipCount++;

            // Safe peak calculation using int32_t (handles -32768 without int16_t overflow)
            int32_t sl = left;
            uint32_t magL = (sl < 0) ? (uint32_t)(-sl) : (uint32_t)sl;
            if (magL > _maxLeftPeak) _maxLeftPeak = magL;

            int32_t sr = right;
            uint32_t magR = (sr < 0) ? (uint32_t)(-sr) : (uint32_t)sr;
            if (magR > _maxRightPeak) _maxRightPeak = magR;

            // 3. Mono selection & statistics
            int16_t sample = (magR > magL) ? right : left;
            _monoStats.count++;
            if (sample < _monoStats.minVal) _monoStats.minVal = sample;
            if (sample > _monoStats.maxVal) _monoStats.maxVal = sample;
            _monoStats.sum += sample;
            _monoStats.sumSq += (uint64_t)((int32_t)sample * (int32_t)sample);
            if (sample != 0) _monoStats.nonZeroCount++;
            if (sample <= -32767 || sample >= 32767) _monoStats.clipCount++;

            if (_previewCount < 30) {
                _previewLeft[_previewCount] = left;
                _previewRight[_previewCount] = right;
                _previewMono[_previewCount] = sample;
                _previewCount++;
            }

            *pcmDest++ = sample;
            _pcmBytesRecorded += sizeof(int16_t);
        }
    }
}

size_t AudioRecorder::stopRecording() {
    if (!_isRecording) return _totalWavBytes;
    _isRecording = false;

    writeWavHeader(_pcmBytesRecorded);
    _totalWavBytes = _pcmBytesRecorded + 44;

    uint32_t durationMs = millis() - _recordStartTime;
    _lastRecordDurationMs = durationMs;
    Serial.printf("[Recorder] >>> STOPPED: %u ms, %u PCM bytes, Left Peak=%u, Right Peak=%u <<<\n",
                  (unsigned int)durationMs, (unsigned int)_pcmBytesRecorded, _maxLeftPeak, _maxRightPeak);

    return _totalWavBytes;
}

void AudioRecorder::logDiagnostics() {
    uint32_t durationMs = millis() - _recordStartTime;
    Serial.println("\n==================== [AUDIO DIAGNOSTICS] ====================");
    Serial.printf("Duration: %u ms | PCM Bytes: %u | Mono Samples: %u\n",
                  (unsigned int)durationMs, (unsigned int)_pcmBytesRecorded, (unsigned int)_monoStats.count);
    Serial.printf("LEFT : RMS=%-7.1f min=%-6d max=%-6d mean=%-6.1f nonzero=%5.1f%% clip=%u (%.2f%%)\n",
                  _leftStats.getRms(), _leftStats.minVal, _leftStats.maxVal,
                  _leftStats.getMean(), _leftStats.getNonZeroPct(),
                  (unsigned int)_leftStats.clipCount, _leftStats.getClipPct());
    Serial.printf("RIGHT: RMS=%-7.1f min=%-6d max=%-6d mean=%-6.1f nonzero=%5.1f%% clip=%u (%.2f%%)\n",
                  _rightStats.getRms(), _rightStats.minVal, _rightStats.maxVal,
                  _rightStats.getMean(), _rightStats.getNonZeroPct(),
                  (unsigned int)_rightStats.clipCount, _rightStats.getClipPct());
    Serial.printf("MONO : RMS=%-7.1f min=%-6d max=%-6d mean=%-6.1f nonzero=%5.1f%% clip=%u (%.2f%%)\n",
                  _monoStats.getRms(), _monoStats.minVal, _monoStats.maxVal,
                  _monoStats.getMean(), _monoStats.getNonZeroPct(),
                  (unsigned int)_monoStats.clipCount, _monoStats.getClipPct());

    Serial.print("First 25 Left samples : ");
    for (size_t i = 0; i < (_previewCount < 25 ? _previewCount : 25); i++) {
        Serial.printf("%d ", _previewLeft[i]);
    }
    Serial.println();

    Serial.print("First 25 Right samples: ");
    for (size_t i = 0; i < (_previewCount < 25 ? _previewCount : 25); i++) {
        Serial.printf("%d ", _previewRight[i]);
    }
    Serial.println();

    Serial.print("First 25 Mono samples : ");
    for (size_t i = 0; i < (_previewCount < 25 ? _previewCount : 25); i++) {
        Serial.printf("%d ", _previewMono[i]);
    }
    Serial.println();

    // Call ES8311 register dump directly
    es8311_codec_dump_registers();
    Serial.println("=============================================================\n");
}

void AudioRecorder::writeWavHeader(size_t pcmBytes) {
    if (!_psramBuffer) return;

    uint32_t totalFileSize = pcmBytes + 36;
    uint32_t byteRate = AUDIO_SAMPLE_RATE * AUDIO_CHANNELS * (AUDIO_BITS_PER_SAMPLE / 8);
    uint16_t blockAlign = AUDIO_CHANNELS * (AUDIO_BITS_PER_SAMPLE / 8);

    uint8_t* h = _psramBuffer;

    // RIFF chunk descriptor
    h[0] = 'R'; h[1] = 'I'; h[2] = 'F'; h[3] = 'F';
    h[4] = (uint8_t)(totalFileSize & 0xFF);
    h[5] = (uint8_t)((totalFileSize >> 8) & 0xFF);
    h[6] = (uint8_t)((totalFileSize >> 16) & 0xFF);
    h[7] = (uint8_t)((totalFileSize >> 24) & 0xFF);
    h[8] = 'W'; h[9] = 'A'; h[10] = 'V'; h[11] = 'E';

    // "fmt " sub-chunk
    h[12] = 'f'; h[13] = 'm'; h[14] = 't'; h[15] = ' ';
    h[16] = 16; h[17] = 0; h[18] = 0; h[19] = 0; // Subchunk1Size (16 for PCM)
    h[20] = 1; h[21] = 0;                         // AudioFormat (1 = PCM)
    h[22] = AUDIO_CHANNELS; h[23] = 0;
    
    // SampleRate (16000)
    h[24] = (uint8_t)(AUDIO_SAMPLE_RATE & 0xFF);
    h[25] = (uint8_t)((AUDIO_SAMPLE_RATE >> 8) & 0xFF);
    h[26] = (uint8_t)((AUDIO_SAMPLE_RATE >> 16) & 0xFF);
    h[27] = (uint8_t)((AUDIO_SAMPLE_RATE >> 24) & 0xFF);

    // ByteRate
    h[28] = (uint8_t)(byteRate & 0xFF);
    h[29] = (uint8_t)((byteRate >> 8) & 0xFF);
    h[30] = (uint8_t)((byteRate >> 16) & 0xFF);
    h[31] = (uint8_t)((byteRate >> 24) & 0xFF);

    // BlockAlign
    h[32] = (uint8_t)(blockAlign & 0xFF);
    h[33] = (uint8_t)((blockAlign >> 8) & 0xFF);

    // BitsPerSample (16)
    h[34] = (uint8_t)(AUDIO_BITS_PER_SAMPLE & 0xFF);
    h[35] = (uint8_t)((AUDIO_BITS_PER_SAMPLE >> 8) & 0xFF);

    // "data" sub-chunk
    h[36] = 'd'; h[37] = 'a'; h[38] = 't'; h[39] = 'a';
    h[40] = (uint8_t)(pcmBytes & 0xFF);
    h[41] = (uint8_t)((pcmBytes >> 8) & 0xFF);
    h[42] = (uint8_t)((pcmBytes >> 16) & 0xFF);
    h[43] = (uint8_t)((pcmBytes >> 24) & 0xFF);
}

void AudioRecorder::playTone(float freqHz, uint32_t durationMs, float volume) {
    if (freqHz <= 0.0f || durationMs == 0) return;
    if (volume < 0.0f) volume = 0.0f;
    if (volume > 1.0f) volume = 1.0f;

    Serial.printf("[Audio] Playing %.1f Hz tone for %u ms (vol=%.2f)...\n", freqHz, (unsigned int)durationMs, volume);

    // 1. Enable FM8002 Power Amplifier (Active-LOW on GPIO 1)
    pinMode(PIN_PA_ENABLE, OUTPUT);
    digitalWrite(PIN_PA_ENABLE, LOW);
    delay(25); // Pop-suppression: allow FM8002 bypass reference cap to stabilize

    const size_t sampleRate = AUDIO_SAMPLE_RATE;
    const size_t totalSamples = (sampleRate * durationMs) / 1000;
    const size_t rampSamples = min((size_t)(sampleRate * 0.005f), totalSamples / 4); // 5ms fade envelope
    const float maxAmp = 32767.0f * volume;
    const float phaseInc = 2.0f * (float)M_PI * freqHz / (float)sampleRate;

    const size_t CHUNK_FRAMES = 128;
    int16_t chunk[CHUNK_FRAMES * 2]; // 16-bit stereo (L + R)

    float phase = 0.0f;
    size_t samplesSent = 0;

    while (samplesSent < totalSamples) {
        size_t framesToGenerate = min(CHUNK_FRAMES, totalSamples - samplesSent);
        for (size_t i = 0; i < framesToGenerate; i++) {
            size_t sampleIdx = samplesSent + i;
            float envelope = 1.0f;
            if (rampSamples > 0) {
                if (sampleIdx < rampSamples) {
                    envelope = (float)sampleIdx / (float)rampSamples;
                } else if (sampleIdx > (totalSamples - rampSamples)) {
                    envelope = (float)(totalSamples - sampleIdx) / (float)rampSamples;
                }
            }

            int16_t sampleVal = (int16_t)(sinf(phase) * maxAmp * envelope);
            chunk[i * 2]     = sampleVal; // Left channel (DAC)
            chunk[i * 2 + 1] = sampleVal; // Right channel (DAC)

            phase += phaseInc;
            if (phase >= 2.0f * (float)M_PI) {
                phase -= 2.0f * (float)M_PI;
            }
        }

        size_t bytesWritten = 0;
        i2s_write(I2S_PORT, chunk, framesToGenerate * 2 * sizeof(int16_t), &bytesWritten, portMAX_DELAY);
        samplesSent += framesToGenerate;
    }

    // Flush zeros to cleanly clear I2S DMA pipeline
    memset(chunk, 0, sizeof(chunk));
    size_t bw = 0;
    i2s_write(I2S_PORT, chunk, sizeof(chunk), &bw, portMAX_DELAY);
    delay(20);

    // 2. Shut down FM8002 PA (Active-LOW, pull HIGH to mute and reduce current)
    digitalWrite(PIN_PA_ENABLE, HIGH);
    Serial.println("[Audio] Tone complete (amplifier muted).");
}

void AudioRecorder::playChime() {
    Serial.println("[Audio] >>> Playing Speaker Test Chime (C5-E5-G5-C6) <<<");

    // Enable amplifier for the entire sequence to prevent click artifacts between notes
    pinMode(PIN_PA_ENABLE, OUTPUT);
    digitalWrite(PIN_PA_ENABLE, LOW);
    delay(30);

    const float notes[] = { 523.25f, 659.25f, 783.99f, 1046.50f }; // C5, E5, G5, C6
    const uint32_t noteDurationMs = 120;
    const float volume = 0.35f;
    const size_t sampleRate = AUDIO_SAMPLE_RATE;
    const float maxAmp = 32767.0f * volume;

    const size_t CHUNK_FRAMES = 128;
    int16_t chunk[CHUNK_FRAMES * 2];

    for (size_t n = 0; n < sizeof(notes)/sizeof(notes[0]); n++) {
        float freqHz = notes[n];
        float phaseInc = 2.0f * (float)M_PI * freqHz / (float)sampleRate;
        float phase = 0.0f;
        size_t totalSamples = (sampleRate * noteDurationMs) / 1000;
        size_t rampSamples = (size_t)(sampleRate * 0.008f); // 8ms envelope
        size_t samplesSent = 0;

        while (samplesSent < totalSamples) {
            size_t frames = min(CHUNK_FRAMES, totalSamples - samplesSent);
            for (size_t i = 0; i < frames; i++) {
                size_t idx = samplesSent + i;
                float env = 1.0f;
                if (idx < rampSamples) {
                    env = (float)idx / (float)rampSamples;
                } else if (idx > (totalSamples - rampSamples)) {
                    env = (float)(totalSamples - idx) / (float)rampSamples;
                }
                int16_t val = (int16_t)(sinf(phase) * maxAmp * env);
                chunk[i * 2]     = val;
                chunk[i * 2 + 1] = val;

                phase += phaseInc;
                if (phase >= 2.0f * (float)M_PI) phase -= 2.0f * (float)M_PI;
            }

            size_t bw = 0;
            i2s_write(I2S_PORT, chunk, frames * 2 * sizeof(int16_t), &bw, portMAX_DELAY);
            samplesSent += frames;
        }

        // Slight 15ms gap between notes
        memset(chunk, 0, sizeof(chunk));
        size_t gapSamples = (sampleRate * 15) / 1000;
        size_t bw = 0;
        i2s_write(I2S_PORT, chunk, min(gapSamples, CHUNK_FRAMES) * 2 * sizeof(int16_t), &bw, portMAX_DELAY);
    }

    // Clear DMA tail
    memset(chunk, 0, sizeof(chunk));
    size_t bw = 0;
    i2s_write(I2S_PORT, chunk, sizeof(chunk), &bw, portMAX_DELAY);
    delay(20);

    // Mute FM8002 PA
    digitalWrite(PIN_PA_ENABLE, HIGH);
    Serial.println("[Audio] Speaker test chime finished.");
}

bool AudioRecorder::playAudioStream(Stream& stream, size_t totalBytes, std::function<bool()> shouldAbort) {
    Serial.println("[Audio] >>> Starting Voice Stream Playback >>>");

    // 1. Enable FM8002 Power Amplifier (Active-LOW on GPIO 1)
    pinMode(PIN_PA_ENABLE, OUTPUT);
    digitalWrite(PIN_PA_ENABLE, LOW);
    delay(30); // Pop-suppression: allow FM8002 bypass reference cap to stabilize

    // 2. Inspect & skip 44-byte WAV header if stream starts with 'RIFF'
    uint8_t header[44];
    size_t headerRead = stream.readBytes((char*)header, 44);
    if (headerRead == 44 && memcmp(header, "RIFF", 4) != 0) {
        // Not a standard RIFF header, write bytes directly to I2S
        size_t bw = 0;
        i2s_write(I2S_PORT, header, 44, &bw, portMAX_DELAY);
    }

    const size_t CHUNK_SIZE = 1024;
    uint8_t buf[CHUNK_SIZE];
    uint32_t lastDataTime = millis();
    size_t totalBytesPlayed = 0;
    bool aborted = false;

    while (stream.available() > 0 || (millis() - lastDataTime < 1500)) {
        if (shouldAbort && shouldAbort()) {
            Serial.println("[Audio] Playback interrupted by user tap.");
            aborted = true;
            break;
        }

        size_t avail = stream.available();
        if (avail > 0) {
            size_t toRead = min(avail, CHUNK_SIZE);
            size_t bytesRead = stream.readBytes((char*)buf, toRead);
            if (bytesRead > 0) {
                size_t bw = 0;
                i2s_write(I2S_PORT, buf, bytesRead, &bw, portMAX_DELAY);
                totalBytesPlayed += bytesRead;
                lastDataTime = millis();
            }
        } else {
            delay(5);
        }
    }

    // 3. Clear DMA pipeline with zeros
    memset(buf, 0, sizeof(buf));
    size_t bw = 0;
    i2s_write(I2S_PORT, buf, min((size_t)512, CHUNK_SIZE), &bw, portMAX_DELAY);
    delay(25);

    // 4. Mute FM8002 PA (Active-LOW, pull HIGH)
    digitalWrite(PIN_PA_ENABLE, HIGH);
    Serial.printf("[Audio] Playback finished (%u bytes streamed, aborted=%s)\n", 
                  (unsigned int)totalBytesPlayed, aborted ? "true" : "false");
    return !aborted;
}


