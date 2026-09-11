<!-- converted from pinout_allocation.xlsx -->

## Sheet: Sheet1
| ESP32-S3芯片IO资源分配表 |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
| 引脚编号 | GPIO | 是否引出 | 片内默认连接说明 | 外部设备连接说明 | 使用说明 |
| 4 | CHIP_PU | N | RESET Pin | 液晶屏复位引脚 | 复位ESP32和液晶屏，低电平复位 |
| 5 | GPIO0 | N | RTC_GPIO0, GPIO0 | BOOT按键 | 没引出，不能做普通IO口使用 |
| 6 | GPIO1 | N | RTC_GPIO1, GPIO1, TOUCH1, ADC1_CH0 | 音频功放IC使能引脚，低电平使能 | 没引出，不能做普通IO口使用 |
| 7 | GPIO2 | Y | RTC_GPIO2, GPIO2, TOUCH2, ADC1_CH1 | 无 | 可做普通IO口使用 |
| 8 | GPIO3 | Y | RTC_GPIO3, GPIO3, TOUCH3, ADC1_CH2 | 无 | 可做普通IO口使用 |
| 9 | GPIO4 | N | RTC_GPIO4, GPIO4, TOUCH4, ADC1_CH3 | 音频I2S主时钟线，用于为整个音频系统提供基准时钟 | 没引出，不能做普通IO口使用 |
| 10 | GPIO5 | N | RTC_GPIO5, GPIO5, TOUCH5, ADC1_CH4 | 音频I2S串行时钟线，它用于确定数据传输的速度和时序 | 没引出，不能做普通IO口使用 |
| 11 | GPIO6 | N | RTC_GPIO6, GPIO6, TOUCH6, ADC1_CH5 | 音频I2S发送音频数据的输出引脚 | 没引出，不能做普通IO口使用 |
| 12 | GPIO7 | N | RTC_GPIO7, GPIO7, TOUCH7, ADC1_CH6 | 音频I2S采样频率。它用于切换左右声道的数据 | 没引出，不能做普通IO口使用 |
| 13 | GPIO8 | N | RTC_GPIO8, GPIO8, TOUCH8, ADC1_CH7, SUBSPICS1 | 音频I2S是接收音频数据的输入引脚 | 没引出，不能做普通IO口使用 |
| 14 | GPIO9 | N | RTC_GPIO9, GPIO9, TOUCH9, ADC1_CH8, SUBSPIHD, FSPIHD | 电池电量ADC值读取引脚 | 没引出，不能做普通IO口使用 |
| 15 | GPIO10 | N | RTC_GPIO10, GPIO10, TOUCH10, ADC1_CH9, FSPIIO4, SUBSPICS0, FSPICS0 | 液晶屏片选引脚，低电平使能 | 没引出，不能做普通IO口使用 |
| 16 | GPIO11 | N | RTC_GPIO11, GPIO11, TOUCH11, ADC2_CH0, 
FSPIIO5, SUBSPID, FSPID | 液晶屏SPI总线写数据引脚 | 没引出，不能做普通IO口使用 |
| 17 | GPIO12 | N | RTC_GPIO12, GPIO12, TOUCH12, ADC2_CH1, FSPIIO6, SUBSPICLK, FSPICLK | 液晶屏SPI总线时钟引脚 | 没引出，不能做普通IO口使用 |
| 18 | GPIO13 | N | RTC_GPIO13, GPIO13, TOUCH13, ADC2_CH2, FSPIIO7, SUBSPIQ, FSPIQ | 液晶屏SPI总线读数据引脚 | 没引出，不能做普通IO口使用 |
| 19 | GPIO14 | Y | RTC_GPIO14, GPIO14, TOUCH14, ADC2_CH3, FSPIDQS, SUBSPIWP, FSPIWP | 无 | 可做普通IO口使用 |
| 21 | GPIO15 | Y | RTC_GPIO15, GPIO15, U0RTS, ADC2_CH4, XTAL_32K_P | 电容触摸屏I2C总线时钟信号引脚
音频编解码IC的I2C总线时钟信号引脚 | 不使用触摸和音频功能时，可做普通IO口或者I2C时钟引脚使用。
如果使用触摸或者音频功能，则只能做I2C时钟引脚使用 |
| 22 | GPIO16 | Y | RTC_GPIO16, GPIO16, U0CTS, ADC2_CH5, XTAL_32K_N | 电容触摸屏I2C总线数据信号引脚
音频编解码IC的I2C总线数据信号引脚 | 不使用触摸和音频功能时，可做普通IO口或者I2C数据引脚使用。
如果使用触摸或者音频功能，则只能做I2C数据引脚使用 |
| 23 | GPIO17 | N | RTC_GPIO17, GPIO17, U1TXD, ADC2_CH6 | 电容触摸屏中断输入引脚，发生触摸事件时，输入低电平 | 没引出，不能做普通IO口使用 |
| 24 | GPIO18 | N | RTC_GPIO18, GPIO18, U1RXD, ADC2_CH7, CLK_OUT3 | 电容触摸屏复位控制引脚，低电平复位 | 没引出，不能做普通IO口使用 |
| 25 | GPIO19 | N | RTC_GPIO19, GPIO19, U1RTS, ADC2_CH8, CLK_OUT2, USB_D- | USB总线差分信号数据线负极引脚 | 没引出，不能做普通IO口使用 |
| 26 | GPIO20 | N | RTC_GPIO20, GPIO20, U1CTS, ADC2_CH9, CLK_OUT1, USB_D+ | USB总线差分信号数据线正极引脚 | 没引出，不能做普通IO口使用 |
| 27 | GPIO21 | Y | RTC_GPIO21, GPIO21 | 无 | 可做普通IO口使用 |
| 28 | GPIO26 | N | SPICS1, GPIO26 | 内部OPI PSRAM占片选引脚，低电平使能 | 内部PSRAM专用，不能做普通IO口使用 |
| 30 | GPIO27 | N | SPIHD, GPIO27 | 外部QSPI FLASH的DATA3引脚
内部OPI PSRAM的DATA3引脚 | 外部FLASH和内部PSRAM专用，不能做普通IO口使用 |
| 31 | GPIO28 | N | SPIWP, GPIO28 | 外部QSPI FLASH的DATA2引脚
内部OPI PSRAM的DATA2引脚 | 外部FLASH和内部PSRAM专用，不能做普通IO口使用 |
| 32 | GPIO29 | N | SPICS0, GPIO29 | 外部QSPI FLASH的的片选引脚，低电平使能 | 外部FLASH专用，不能做普通IO口使用 |
| 33 | GPIO30 | N | SPICLK, GPIO30 | 外部QSPI FLASH的时钟引脚
内部OPI PSRAM的时钟引脚 | 外部FLASH和内部PSRAM专用，不能做普通IO口使用 |
| 34 | GPIO31 | N | SPIQ, GPIO31 | 外部QSPI FLASH的DATA1引脚
内部OPI PSRAM的DATA1引脚 | 外部FLASH和内部PSRAM专用，不能做普通IO口使用 |
| 35 | GPIO32 | N | SPID, GPIO32 | 外部QSPI FLASH的DATA0引脚
内部OPI PSRAM的DATA0引脚 | 外部FLASH和内部PSRAM专用，不能做普通IO口使用 |
| 36 | GPIO48 | N | SPICLK_N_DIFF, GPIO48, SUBSPICLK_N_DIFF | SD卡SDIO总线数据DATA2引脚 | 没引出，不能做普通IO口使用 |
| 37 | GPIO47 | N | SPICLK_P_DIFF, GPIO47, SUBSPICLK_P_DIFF | SD卡SDIO总线数据DATA3引脚 | 没引出，不能做普通IO口使用 |
| 38 | GPIO33 | N | SPIIO4, GPIO33, FSPIHD, SUBSPIHD | 内部OPI PSRAM的DATA4引脚 | 内部PSRAM专用，不能做普通IO口使用 |
| 39 | GPIO34 | N | SPIIO5, GPIO34, FSPICS0, SUBSPICS0 | 内部OPI PSRAM的DATA5引脚 | 内部PSRAM专用，不能做普通IO口使用 |
| 40 | GPIO35 | N | SPIIO6, GPIO35, FSPID, SUBSPID | 内部OPI PSRAM的DATA6引脚 | 内部PSRAM专用，不能做普通IO口使用 |
| 41 | GPIO36 | N | SPIIO7, GPIO36, FSPICLK, SUBSPICLK | 内部OPI PSRAM的DATA7引脚 | 内部PSRAM专用，不能做普通IO口使用 |
| 42 | GPIO37 | N | SPIDQS, GPIO37, FSPIQ, SUBSPIQ | 内部OPI PSRAM的数据掩码和数据时钟读取引脚 | 内部PSRAM专用，不能做普通IO口使用 |
| 43 | IO38 | N | GPIO38, FSPIWP, SUBSPIWP | SD卡SDIO总线时钟引脚 | 没引出，不能做普通IO口使用 |
| 44 | IO39 | N | MTCK, GPIO39, CLK_OUT3, SUBSPICS1 | SD卡SDIO总线数据DATA0引脚 | 没引出，不能做普通IO口使用 |
| 45 | IO40 | N | MTDO, GPIO40, CLK_OUT2 | SD卡SDIO总线命令引脚 | 没引出，不能做普通IO口使用 |
| 47 | IO41 | N | MTDI, GPIO41, CLK_OUT1 | SD卡SDIO总线数据DATA1引脚 | 没引出，不能做普通IO口使用 |
| 48 | IO42 | N | MTMS, GPIO42 | 单线RGB三色LED灯控制引脚 | 没引出，不能做普通IO口使用 |
| 49 | IO43 | Y | U0TXD, GPIO43, CLK_OUT1 | ESP32-S3串口0发送数据引脚 | 不使用串口通信时可做普通IO口使用 |
| 50 | IO44 | Y | U0RXD, GPIO44, CLK_OUT2 | ESP32-S3串口0接受数据引脚 | 不使用串口通信时可做普通IO口使用 |
| 51 | IO45 | N | GPIO45 | 液晶屏背光控制引脚，高电平点亮背光 | 没引出，不能做普通IO口使用 |
| 52 | IO46 | N | GPIO46 | 液晶屏命令/数据选择控制引脚，高电平：数据；低电平：命令 | 没引出，不能做普通IO口使用 |