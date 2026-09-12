#pragma once
#include <Arduino.h>

#define AUDIO_SAMPLE_RATE     16000
#define AUDIO_BITS_PER_SAMPLE 16
#define AUDIO_CHANNELS        1
#define MAX_RECORD_SECONDS    15
#define MAX_AUDIO_BUFFER_SIZE (AUDIO_SAMPLE_RATE * sizeof(int16_t) * MAX_RECORD_SECONDS + 44)

#include <functional>

struct ChannelStats {
    size_t count;
    int16_t minVal;
    int16_t maxVal;
    int64_t sum;
    uint64_t sumSq;
    size_t nonZeroCount;
    size_t clipCount;

    void reset() {
        count = 0;
        minVal = 32767;
        maxVal = -32768;
        sum = 0;
        sumSq = 0;
        nonZeroCount = 0;
        clipCount = 0;
    }

    double getMean() const { return count > 0 ? (double)sum / (double)count : 0.0; }
    double getRms() const { return count > 0 ? sqrt((double)sumSq / (double)count) : 0.0; }
    double getNonZeroPct() const { return count > 0 ? (100.0 * (double)nonZeroCount / (double)count) : 0.0; }
    double getClipPct() const { return count > 0 ? (100.0 * (double)clipCount / (double)count) : 0.0; }
};

class AudioRecorder {
public:
    AudioRecorder();
    bool begin();
    bool startRecording();
    void update(); // Call in loop() while recording
    size_t stopRecording(); // Returns total WAV bytes
    void logDiagnostics(); // Print full per-channel analysis and codec registers
    
    // Speaker Audio Playback / Test Methods
    void playTone(float freqHz, uint32_t durationMs, float volume = 0.35f);
    void playChime();
    bool playAudioStream(Stream& stream, size_t totalBytes = 0, std::function<bool()> shouldAbort = nullptr);
    
    bool isRecording() const { return _isRecording; }
    uint32_t getRecordDurationMs() const {
        return _isRecording ? (millis() - _recordStartTime) : _lastRecordDurationMs;
    }
    uint8_t* getWavBuffer() { return _psramBuffer; }
    size_t getWavSize() const { return _totalWavBytes; }
    uint32_t getMaxLeft() const { return _maxLeftPeak; }
    uint32_t getMaxRight() const { return _maxRightPeak; }

    const ChannelStats& getLeftStats() const { return _leftStats; }
    const ChannelStats& getRightStats() const { return _rightStats; }
    const ChannelStats& getMonoStats() const { return _monoStats; }

private:
    uint8_t* _psramBuffer;
    size_t _pcmBytesRecorded;
    size_t _totalWavBytes;
    bool _isRecording;
    uint32_t _recordStartTime;
    uint32_t _lastRecordDurationMs;
    uint32_t _maxLeftPeak;
    uint32_t _maxRightPeak;

    ChannelStats _leftStats;
    ChannelStats _rightStats;
    ChannelStats _monoStats;

    int16_t _previewLeft[32];
    int16_t _previewRight[32];
    int16_t _previewMono[32];
    size_t _previewCount;

    void writeWavHeader(size_t pcmBytes);
};

extern AudioRecorder recorder;
