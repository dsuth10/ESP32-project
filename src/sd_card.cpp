#include "sd_card.h"
#include <algorithm>

static SDCardStatus g_sdStatus = {
  false, false, "None", 0.0f, 0.0f, 0.0f, false
};

static String getCardTypeString(sdcard_type_t type) {
  switch (type) {
    case CARD_MMC:  return "MMC";
    case CARD_SD:   return "SDSC";
    case CARD_SDHC: return "SDHC/SDXC";
    case CARD_UNKNOWN: return "UNKNOWN";
    case CARD_NONE:
    default:        return "No Card";
  }
}

bool sdCardInit(bool formatIfFailed) {
  Serial.println("\n[SD] Initializing SD_MMC (SDIO) controller...");

  if (g_sdStatus.mounted) {
    SD_MMC.end();
    g_sdStatus.mounted = false;
  }

  // Enable internal pullups on CMD and data lines
  pinMode(PIN_SD_CMD, INPUT_PULLUP);
  pinMode(PIN_SD_D0, INPUT_PULLUP);
  pinMode(PIN_SD_D1, INPUT_PULLUP);
  pinMode(PIN_SD_D2, INPUT_PULLUP);
  pinMode(PIN_SD_D3, INPUT_PULLUP);

  bool mounted = false;

  // Attempt 1: 4-bit wide SDIO mode at 20MHz
  Serial.printf("[SD] Probing 4-bit SDIO mode at 20MHz (CLK:%d, CMD:%d, D0:%d, D1:%d, D2:%d, D3:%d)...\n",
                PIN_SD_CLK, PIN_SD_CMD, PIN_SD_D0, PIN_SD_D1, PIN_SD_D2, PIN_SD_D3);
  SD_MMC.setPins(PIN_SD_CLK, PIN_SD_CMD, PIN_SD_D0, PIN_SD_D1, PIN_SD_D2, PIN_SD_D3);
  mounted = SD_MMC.begin("/sdcard", false /* 4-bit */, formatIfFailed, 20000);

  if (mounted && SD_MMC.cardType() == CARD_NONE) {
    mounted = false;
    SD_MMC.end();
  }

  if (mounted) {
    g_sdStatus.is4BitMode = true;
    Serial.println("[SD] >>> Successfully mounted in 4-bit SDIO mode! <<<");
  } else {
    // Attempt 2: 1-bit fallback mode
    Serial.println("[SD] 4-bit mode unsuccessful. Trying 1-bit SDIO mode (CLK, CMD, D0)...");
    SD_MMC.end();
    pinMode(PIN_SD_CMD, INPUT_PULLUP);
    pinMode(PIN_SD_D0, INPUT_PULLUP);
    SD_MMC.setPins(PIN_SD_CLK, PIN_SD_CMD, PIN_SD_D0);
    mounted = SD_MMC.begin("/sdcard", true /* 1-bit */, formatIfFailed, 20000);
    if (mounted) {
      g_sdStatus.is4BitMode = false;
      Serial.println("[SD] >>> Successfully mounted in 1-bit SDIO mode! <<<");
    }
  }

  if (!mounted) {
    Serial.println("[SD] [ERROR] Failed to mount SD card in both 4-bit and 1-bit modes.");
    g_sdStatus.mounted = false;
    g_sdStatus.cardTypeStr = "Mount Failed";
    return false;
  }

  g_sdStatus.mounted = true;
  sdcard_type_t cardType = SD_MMC.cardType();
  g_sdStatus.cardTypeStr = getCardTypeString(cardType);

  uint64_t sizeBytes = SD_MMC.cardSize();
  g_sdStatus.totalBytesGB = (float)sizeBytes / (1024.0f * 1024.0f * 1024.0f);
  Serial.printf("[SD] Card Type: %s | Hardware Capacity: %.2f GB\n", 
                g_sdStatus.cardTypeStr.c_str(), g_sdStatus.totalBytesGB);

  // Set up standard directories
  sdCardEnsureDirectories();
  return true;
}

bool sdCardFormat() {
  Serial.println("\n[SD Format] Starting FAT32 format routine on SD card...");
  if (g_sdStatus.mounted) {
    SD_MMC.end();
    g_sdStatus.mounted = false;
  }

  pinMode(PIN_SD_CMD, INPUT_PULLUP);
  pinMode(PIN_SD_D0, INPUT_PULLUP);
  SD_MMC.setPins(PIN_SD_CLK, PIN_SD_CMD, PIN_SD_D0);

  // Format via 1-bit SDIO mode with format_if_mount_failed=true
  bool ok = SD_MMC.begin("/sdcard", true /* 1-bit */, true /* format */, 20000);
  if (!ok) {
    Serial.println("[SD Format] [FAIL] Formatting operation failed.");
    return false;
  }

  g_sdStatus.mounted = true;
  g_sdStatus.is4BitMode = false;
  g_sdStatus.cardTypeStr = getCardTypeString(SD_MMC.cardType());
  g_sdStatus.totalBytesGB = (float)SD_MMC.cardSize() / (1024.0f * 1024.0f * 1024.0f);

  Serial.println("[SD Format] >>> SUCCESS: SD card formatted as FAT32! <<<");
  sdCardEnsureDirectories();
  printSDCardInfo();
  return true;
}

bool sdCardEnsureDirectories() {
  if (!g_sdStatus.mounted) return false;

  if (!SD_MMC.exists("/recordings")) {
    SD_MMC.mkdir("/recordings");
    Serial.println("[SD] Created folder: /recordings");
  }
  if (!SD_MMC.exists("/chat")) {
    SD_MMC.mkdir("/chat");
    Serial.println("[SD] Created folder: /chat");
  }
  if (!SD_MMC.exists("/config")) {
    SD_MMC.mkdir("/config");
    Serial.println("[SD] Created folder: /config");
  }

  // Create default README
  if (!SD_MMC.exists("/README.txt")) {
    File f = SD_MMC.open("/README.txt", FILE_WRITE);
    if (f) {
      f.println("ESP32-S3 MacroPad & Voice Satellite Storage");
      f.println("===========================================");
      f.println("- /recordings/ : Offline audio .wav logs");
      f.println("- /chat/       : Conversation transcripts (history.txt)");
      f.println("- /config/     : Custom macro JSON definitions");
      f.close();
      Serial.println("[SD] Created /README.txt");
    }
  }

  // Create default chat history log if missing
  if (!SD_MMC.exists("/chat/history.txt")) {
    File f = SD_MMC.open("/chat/history.txt", FILE_WRITE);
    if (f) {
      f.println("=== Hermes & MacroPad Conversation History ===");
      f.close();
      Serial.println("[SD] Initialized /chat/history.txt");
    }
  }

  // Create default macro config if missing
  if (!SD_MMC.exists("/config/macros.json")) {
    File f = SD_MMC.open("/config/macros.json", FILE_WRITE);
    if (f) {
      f.println("{\n  \"version\": 1,\n  \"device\": \"ESP32 MacroPad\",\n  \"profiles\": [\n    {\"name\": \"Media & Audio\", \"page\": 1},\n    {\"name\": \"Productivity\", \"page\": 2},\n    {\"name\": \"Windows Tools\", \"page\": 3},\n    {\"name\": \"Chat & Typing\", \"page\": 4}\n  ]\n}");
      f.close();
      Serial.println("[SD] Created default /config/macros.json");
    }
  }

  return true;
}

bool sdCardRunSelfTest() {
  if (!g_sdStatus.mounted) {
    Serial.println("[SD Test] [FAIL] Card is not mounted.");
    return false;
  }

  Serial.println("\n--- [SD Card Self-Test Routine] ---");
  Serial.printf("[SD Test] Card Type: %s\n", g_sdStatus.cardTypeStr.c_str());
  Serial.printf("[SD Test] Total Capacity: %.2f GB\n", g_sdStatus.totalBytesGB);

  // Step 1: Test File Creation & Write
  const char* testPath = "/sd_test.txt";
  Serial.printf("[SD Test] Creating test file: %s ...\n", testPath);

  File file = SD_MMC.open(testPath, FILE_WRITE);
  if (!file) {
    Serial.println("[SD Test] [FAIL] Unable to open test file for writing.");
    Serial.println("[SD Test] Hint: Use command 'sd_format' to format the blank card in FAT32.");
    g_sdStatus.selfTestPassed = false;
    return false;
  }

  uint32_t now = millis();
  file.printf("ESP32-S3 MacroPad SD Test OK | Uptime=%lu ms | Mode=%s\n",
              (unsigned long)now, g_sdStatus.is4BitMode ? "4-bit" : "1-bit");
  file.close();
  Serial.println("[SD Test] File write completed successfully. [OK]");

  // Step 2: Test File Read & Verification
  Serial.printf("[SD Test] Reading back file: %s ...\n", testPath);
  file = SD_MMC.open(testPath, FILE_READ);
  if (!file) {
    Serial.println("[SD Test] [FAIL] Unable to open test file for reading.");
    g_sdStatus.selfTestPassed = false;
    return false;
  }

  String readBack = file.readStringUntil('\n');
  readBack.trim();
  file.close();

  Serial.printf("[SD Test] Readback content: \"%s\"\n", readBack.c_str());

  if (readBack.indexOf("ESP32-S3 MacroPad SD Test OK") >= 0) {
    Serial.println("[SD Test] >>> SELF-TEST PASSED: SD read/write integrity verified! <<<");
    g_sdStatus.selfTestPassed = true;
    return true;
  } else {
    Serial.println("[SD Test] [FAIL] Readback payload content mismatch.");
    g_sdStatus.selfTestPassed = false;
    return false;
  }
}

bool saveRecordingToSD(const uint8_t* wavData, size_t wavSize, String& outFilename) {
  if (!g_sdStatus.mounted || wavData == nullptr || wavSize == 0) return false;

  sdCardEnsureDirectories();

  static uint32_t s_recIndex = 1;
  char path[48];
  snprintf(path, sizeof(path), "/recordings/rec_%04lu.wav", (unsigned long)s_recIndex++);

  File file = SD_MMC.open(path, FILE_WRITE);
  if (!file) {
    Serial.printf("[SD] Failed to open %s for writing\n", path);
    return false;
  }

  size_t written = file.write(wavData, wavSize);
  file.close();

  if (written == wavSize) {
    outFilename = String(path);
    Serial.printf("[SD] Saved voice recording (%u bytes) -> %s\n", (unsigned int)wavSize, path);
    return true;
  } else {
    Serial.printf("[SD] Partial write: %u of %u bytes\n", (unsigned int)written, (unsigned int)wavSize);
    return false;
  }
}

bool appendChatLog(const String& userTranscript, const String& aiResponse) {
  if (!g_sdStatus.mounted) return false;

  sdCardEnsureDirectories();

  File file = SD_MMC.open("/chat/history.txt", FILE_APPEND);
  if (!file) {
    file = SD_MMC.open("/chat/history.txt", FILE_WRITE);
  }
  if (!file) {
    Serial.println("[SD] Failed to open /chat/history.txt for appending.");
    return false;
  }

  file.printf("[%lu ms]\n", (unsigned long)millis());
  file.printf("USER: %s\n", userTranscript.c_str());
  file.printf("AI  : %s\n", aiResponse.c_str());
  file.println("----------------------------------------");
  file.close();

  Serial.println("[SD] Appended conversation turn to /chat/history.txt");
  return true;
}

String loadMacroConfig() {
  if (!g_sdStatus.mounted) return "";
  File f = SD_MMC.open("/config/macros.json", FILE_READ);
  if (!f) return "";
  String content = f.readString();
  f.close();
  return content;
}

bool saveMacroConfig(const String& jsonContent) {
  if (!g_sdStatus.mounted) return false;
  sdCardEnsureDirectories();
  File f = SD_MMC.open("/config/macros.json", FILE_WRITE);
  if (!f) return false;
  f.print(jsonContent);
  f.close();
  return true;
}

SDCardStatus getSDCardStatus() {
  return g_sdStatus;
}

void printSDCardInfo() {
  if (!g_sdStatus.mounted) {
    Serial.println("[SD] Status: Not mounted.");
    return;
  }
  Serial.println("==========================================");
  Serial.println("          SD Card Hardware Telemetry      ");
  Serial.println("==========================================");
  Serial.printf("  Bus Mode     : %s SDIO\n", g_sdStatus.is4BitMode ? "4-Bit (High Speed)" : "1-Bit");
  Serial.printf("  Card Type    : %s\n", g_sdStatus.cardTypeStr.c_str());
  Serial.printf("  Card Capacity: %.2f GB\n", g_sdStatus.totalBytesGB);
  Serial.println("==========================================");
}

void listSDCardDirectory(const char* dirName, uint8_t levels) {
  if (!g_sdStatus.mounted) {
    Serial.println("[SD] Cannot list directory: SD card not mounted.");
    return;
  }

  Serial.printf("\n[SD] Directory listing for: %s\n", dirName);
  File root = SD_MMC.open(dirName);
  if (!root || !root.isDirectory()) {
    Serial.println("[SD] Failed to open directory.");
    return;
  }

  File file = root.openNextFile();
  int fileCount = 0;
  while (file) {
    if (file.isDirectory()) {
      Serial.printf("  [DIR]  %s\n", file.name());
      if (levels > 0) {
        listSDCardDirectory(file.path(), levels - 1);
      }
    } else {
      Serial.printf("  [FILE] %-24s  (%u bytes)\n", file.name(), (unsigned int)file.size());
    }
    fileCount++;
    file = root.openNextFile();
  }
  if (fileCount == 0) {
    Serial.println("  (Empty directory)");
  }
}

bool sdCardGetStorageSpace(float& outTotalGB, float& outFreeGB, float& outUsedMB) {
  if (!g_sdStatus.mounted) {
    outTotalGB = 0.0f;
    outFreeGB = 0.0f;
    outUsedMB = 0.0f;
    return false;
  }

  uint64_t cardSizeBytes = SD_MMC.cardSize();
  uint64_t totalBytes = SD_MMC.totalBytes();
  uint64_t usedBytes = SD_MMC.usedBytes();

  if (totalBytes == 0) {
    totalBytes = cardSizeBytes;
  }

  outTotalGB = (float)cardSizeBytes / (1024.0f * 1024.0f * 1024.0f);
  outUsedMB = (float)usedBytes / (1024.0f * 1024.0f);

  if (totalBytes > usedBytes) {
    outFreeGB = (float)(totalBytes - usedBytes) / (1024.0f * 1024.0f * 1024.0f);
  } else {
    outFreeGB = outTotalGB;
  }
  return true;
}

static String formatSizeString(size_t bytes) {
  if (bytes < 1024) {
    return String(bytes) + " B";
  } else if (bytes < 1024 * 1024) {
    return String(bytes / 1024.0f, 1) + " KB";
  } else {
    return String(bytes / (1024.0f * 1024.0f), 1) + " MB";
  }
}

std::vector<SDFileEntry> sdCardListDirectory(const String& dirPath) {
  std::vector<SDFileEntry> dirs;
  std::vector<SDFileEntry> files;

  if (!g_sdStatus.mounted) return dirs;

  File root = SD_MMC.open(dirPath);
  if (!root || !root.isDirectory()) return dirs;

  File file = root.openNextFile();
  while (file) {
    SDFileEntry entry;
    const char* rawName = file.name();
    String nameStr = String(rawName);
    int lastSlash = nameStr.lastIndexOf('/');
    if (lastSlash >= 0) {
      nameStr = nameStr.substring(lastSlash + 1);
    }
    // Filter out empty names, FAT self/parent links, and hidden/system metadata
    if (nameStr.isEmpty() || nameStr == "." || nameStr == ".." || 
        nameStr.startsWith("._") || nameStr == "System Volume Information") {
      file = root.openNextFile();
      continue;
    }

    entry.name = nameStr;
    entry.isDirectory = file.isDirectory();
    entry.size = file.size();
    if (entry.isDirectory) {
      entry.formattedSize = "<DIR>";
      dirs.push_back(entry);
    } else {
      entry.formattedSize = formatSizeString(entry.size);
      files.push_back(entry);
    }
    file = root.openNextFile();
  }
  root.close();

  // Sort directories and files alphabetically (case-insensitive)
  std::sort(dirs.begin(), dirs.end(), [](const SDFileEntry& a, const SDFileEntry& b) {
    String aLower = a.name; aLower.toLowerCase();
    String bLower = b.name; bLower.toLowerCase();
    return aLower.compareTo(bLower) < 0;
  });
  std::sort(files.begin(), files.end(), [](const SDFileEntry& a, const SDFileEntry& b) {
    String aLower = a.name; aLower.toLowerCase();
    String bLower = b.name; bLower.toLowerCase();
    return aLower.compareTo(bLower) < 0;
  });

  // Combine: directories first, then files
  dirs.insert(dirs.end(), files.begin(), files.end());
  return dirs;
}

