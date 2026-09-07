#pragma once
#include <Arduino.h>

#define AUDIO_SAMPLE_RATE     16000
#define AUDIO_BITS_PER_SAMPLE 16
#define AUDIO_CHANNELS        1
#define MAX_RECORD_SECONDS    15
#define MAX_AUDIO_BUFFER_SIZE (AUDIO_SAMPLE_RATE * sizeof(int16_t) * MAX_RECORD_SECONDS + 44)

class AudioRecorder {
public:
    AudioRecorder();
    bool begin();
    bool startRecording();
    void update(); // Call in loop() while recording
    size_t stopRecording(); // Returns total WAV bytes
    
    bool isRecording() const { return _isRecording; }
    uint32_t getRecordDurationMs() const;
    uint8_t* getWavBuffer() { return _psramBuffer; }
    size_t getWavSize() const { return _totalWavBytes; }
    int16_t getMaxLeft() const { return _maxLeftPeak; }
    int16_t getMaxRight() const { return _maxRightPeak; }

private:
    uint8_t* _psramBuffer;
    size_t _pcmBytesRecorded;
    size_t _totalWavBytes;
    bool _isRecording;
    uint32_t _recordStartTime;
    int16_t _maxLeftPeak;
    int16_t _maxRightPeak;

    void writeWavHeader(size_t pcmBytes);
};

extern AudioRecorder recorder;
