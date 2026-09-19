#pragma once
#include <Arduino.h>
#include <FS.h>
#include <SD_MMC.h>
#include "macropad_config.h"

struct SDCardStatus {
  bool mounted;
  bool selfTestPassed;
  String cardTypeStr;
  float totalBytesGB;
  float usedBytesMB;
  float freeBytesMB;
  bool is4BitMode;
};

// Initializes the SD card in SDIO mode (formats as FAT32 if unformatted/blank)
bool sdCardInit(bool formatIfFailed = true);

// Explicitly format the card as FAT32 and set up directory structure
bool sdCardFormat();

// Ensures default directory structure exists (/recordings, /chat, /config)
bool sdCardEnsureDirectories();

// Runs a self-test: creates, writes, reads back, and verifies a test file
bool sdCardRunSelfTest();

// Saves a PCM/WAV buffer to /recordings/rec_XXXX.wav
bool saveRecordingToSD(const uint8_t* wavData, size_t wavSize, String& outFilename);

// Appends a user prompt and AI response to /chat/history.txt
bool appendChatLog(const String& userTranscript, const String& aiResponse);

// Loads custom macro JSON configuration from /config/macros.json
String loadMacroConfig();

// Saves custom macro JSON configuration to /config/macros.json
bool saveMacroConfig(const String& jsonContent);

struct SDFileEntry {
  String name;
  bool isDirectory;
  size_t size;
  String formattedSize;
};

// Retrieves real-time storage space metrics (Total GB, Free GB, Used MB)
bool sdCardGetStorageSpace(float& outTotalGB, float& outFreeGB, float& outUsedMB);

// Returns sorted list of entries in directory (directories first, then files)
std::vector<SDFileEntry> sdCardListDirectory(const String& dirPath);

// Retrieves the latest status struct
SDCardStatus getSDCardStatus();

// Prints full diagnostics to Serial
void printSDCardInfo();

// Lists contents of directory to Serial
void listSDCardDirectory(const char* dirName = "/", uint8_t levels = 1);

