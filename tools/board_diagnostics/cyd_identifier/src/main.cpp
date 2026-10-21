// Bounded CYD diagnostic. No networking, filesystem, NVS or SD-card writes.
// Pin map: witnessmenow/ESP32-Cheap-Yellow-Display DisplayConfig/CYD2USB.
#include <Arduino.h>
#include <SPI.h>
#include <esp_err.h>
// Skip Arduino's NVS initialisation (which can otherwise migrate/erase old NVS).
// This diagnostic never uses NVS, Wi-Fi or Bluetooth.
extern "C" esp_err_t __wrap_nvs_flash_init() { return ESP_OK; }
SPIClass lcd(HSPI), touch(VSPI);
constexpr int CS=15, DC=2, BL=21, TCS=33;
bool invert=false, st=false;
void cmd(uint8_t c, const uint8_t *p=nullptr, size_t n=0) {
  lcd.beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE0));
  digitalWrite(CS,LOW); digitalWrite(DC,LOW); lcd.transfer(c);
  digitalWrite(DC,HIGH); while(n--) lcd.transfer(*p++);
  digitalWrite(CS,HIGH); lcd.endTransaction();
}
void reg(uint8_t c, std::initializer_list<uint8_t> p) {cmd(c,p.begin(),p.size());}
void readReg(uint8_t c) {
  lcd.beginTransaction(SPISettings(500000,MSBFIRST,SPI_MODE0));
  digitalWrite(CS,LOW);digitalWrite(DC,LOW);lcd.transfer(c);digitalWrite(DC,HIGH);
  Serial.printf("LCD register %02X:",c);
  for(int i=0;i<6;i++) Serial.printf(" %02X",lcd.transfer(0));
  Serial.println();digitalWrite(CS,HIGH);lcd.endTransaction();
}
void rect(int x,int y,int w,int h,uint16_t colour) {
  reg(0x2A,{uint8_t(x>>8),uint8_t(x),uint8_t((x+w-1)>>8),uint8_t(x+w-1)});
  reg(0x2B,{uint8_t(y>>8),uint8_t(y),uint8_t((y+h-1)>>8),uint8_t(y+h-1)});
  lcd.beginTransaction(SPISettings(10000000,MSBFIRST,SPI_MODE0));
  digitalWrite(CS,LOW);digitalWrite(DC,LOW);lcd.transfer(0x2C);digitalWrite(DC,HIGH);
  for(int i=0;i<w*h;i++){lcd.transfer(colour>>8);lcd.transfer(colour&255);}
  digitalWrite(CS,HIGH);lcd.endTransaction();
}
void pattern() {
  cmd(invert?0x21:0x20);
  rect(0,0,240,320,0); // black background and white border
  rect(0,0,240,3,0xffff);rect(0,317,240,3,0xffff);
  rect(0,0,3,320,0xffff);rect(237,0,3,320,0xffff);
  rect(10,60,70,200,0xf800);rect(85,60,70,200,0x07e0);rect(160,60,70,200,0x001f);
  // White mode marker: one square = A (ILI9341); two squares = B (ST7789).
  rect(20,15,20,20,0xffff);if(st)rect(50,15,20,20,0xffff);
  // Unequal corner markers establish orientation.
  rect(10,280,10,10,0xffff);rect(210,280,20,20,0xffff);
  Serial.printf("PATTERN mode=%s inversion=%s; portrait top: %s white square(s); stripes RED GREEN BLUE; black background, white border\n",st?"B-ST7789":"A-ILI9341",invert?"ON":"OFF",st?"two":"one");
}
void initDisplay(bool useST) {
  st=useST; cmd(0x01);delay(150);cmd(0x11);delay(150);
  if(st) {
    reg(0xB2,{0x0c,0x0c,0,0x33,0x33});reg(0xB7,{0x35});reg(0xBB,{0x19});
    reg(0xC0,{0x2c});reg(0xC2,{1});reg(0xC3,{0x12});reg(0xC4,{0x20});reg(0xC6,{0x0f});reg(0xD0,{0xa4,0xa1});
  } else {
    reg(0xCB,{0x39,0x2c,0,0x34,2});reg(0xCF,{0,0xc1,0x30});reg(0xE8,{0x85,0,0x78});
    reg(0xEA,{0,0});reg(0xED,{0x64,3,0x12,0x81});reg(0xF7,{0x20});
    reg(0xC0,{0x23});reg(0xC1,{0x10});reg(0xC5,{0x3e,0x28});reg(0xC7,{0x86});
    reg(0xB1,{0,0x18});reg(0xB6,{8,0x82,0x27});reg(0xF2,{0});reg(0x26,{1});
  }
  reg(0x36,{0x48});reg(0x3A,{0x55});cmd(0x13);cmd(0x29);delay(100);
  digitalWrite(BL,HIGH);pattern();
}
uint16_t adc(uint8_t command) {
  digitalWrite(TCS,LOW);touch.transfer(command);uint16_t v=touch.transfer16(0);digitalWrite(TCS,HIGH);
  return (v>>3)&4095;
}
void setup() {
  Serial.begin(115200);delay(1000);
  Serial.printf("CYD-DIAG-1 chip=%s rev=%d flash=%u heap=%u\n",ESP.getChipModel(),ESP.getChipRevision(),ESP.getFlashChipSize(),ESP.getFreeHeap());
  pinMode(CS,OUTPUT);digitalWrite(CS,HIGH);pinMode(DC,OUTPUT);pinMode(BL,OUTPUT);digitalWrite(BL,LOW);
  pinMode(TCS,OUTPUT);digitalWrite(TCS,HIGH);pinMode(36,INPUT);
  lcd.begin(14,12,13,CS);touch.begin(25,39,32,TCS);
  for(uint8_t r: {0x04,0x09,0xD3,0xDA,0xDB,0xDC})readReg(r);
  initDisplay(true);
  Serial.println("Commands: A=ILI9341; B=ST7789; I=toggle inversion; R=registers. Touch screen to report raw coordinates. No automatic profile switching.");
}
void loop() {
  if(Serial.available())switch(toupper(Serial.read())) {
    case 'A':initDisplay(false);break;case 'B':initDisplay(true);break;
    case 'I':invert=!invert;pattern();break;
    case 'R':for(uint8_t r:{0x04,0x09,0xD3,0xDA,0xDB,0xDC})readReg(r);break;
  }
  static uint32_t last=0;
  if(millis()-last>150 && digitalRead(36)==LOW) {
    last=millis();touch.beginTransaction(SPISettings(500000,MSBFIRST,SPI_MODE0));
    uint16_t x=adc(0xD0),y=adc(0x90),z1=adc(0xB0),z2=adc(0xC0);
    touch.endTransaction();
    Serial.printf("TOUCH irq=0 x=%u y=%u z1=%u z2=%u\n",x,y,z1,z2);
  }
  delay(10);
}
