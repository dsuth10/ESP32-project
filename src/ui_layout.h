#pragma once

// Compile-time UI orientation. One of UI_PORTRAIT or UI_LANDSCAPE must be set
// via platformio.ini build_flags. Default to landscape if neither is provided.
#if !defined(UI_PORTRAIT) && !defined(UI_LANDSCAPE)
  #define UI_LANDSCAPE 1
#endif

#if defined(UI_PORTRAIT) && defined(UI_LANDSCAPE)
  #error "Define only one of UI_PORTRAIT or UI_LANDSCAPE"
#endif

// ---------------------------------------------------------------------------
// Orientation & panel geometry
// ---------------------------------------------------------------------------
#if defined(UI_PORTRAIT)

#define SCREEN_WIDTH       240
#define SCREEN_HEIGHT      320
#define UI_TFT_ROTATION    0          // TFT_eSPI native portrait
#define UI_TOUCH_ROTATION  0          // FT6336 ROTATION_NORMAL

#define UI_SYSTEM_BAR_H    30
#define UI_TITLE_BAR_H     24
#define STATUS_BAR_H       (UI_SYSTEM_BAR_H + UI_TITLE_BAR_H)

#define GRID_ROWS          3
#define GRID_COLS          2

#else // UI_LANDSCAPE

#define SCREEN_WIDTH       320
#define SCREEN_HEIGHT      240
#define UI_TFT_ROTATION    1          // TFT_eSPI landscape
#define UI_TOUCH_ROTATION  1          // FT6336 ROTATION_RIGHT

#define UI_SYSTEM_BAR_H    32
#define UI_TITLE_BAR_H     0
#define STATUS_BAR_H       UI_SYSTEM_BAR_H

#define GRID_ROWS          2
#define GRID_COLS          3

#endif

#define UI_CONTENT_TOP     STATUS_BAR_H
#define UI_CONTENT_H       (SCREEN_HEIGHT - STATUS_BAR_H)

// ---------------------------------------------------------------------------
// Status / chrome
// ---------------------------------------------------------------------------
#if defined(UI_PORTRAIT)

#define UI_NAV_PREV_X      156
#define UI_NAV_PREV_Y      3
#define UI_NAV_PREV_W      24
#define UI_NAV_PREV_H      24
#define UI_NAV_PAGE_CX     192
#define UI_NAV_NEXT_X      208
#define UI_NAV_NEXT_Y      3
#define UI_NAV_NEXT_W      22
#define UI_NAV_NEXT_H      24

#define UI_NAV_PREV_HIT_X0 152
#define UI_NAV_PREV_HIT_X1 184
#define UI_NAV_NEXT_HIT_X0 204
#define UI_NAV_NEXT_HIT_X1 240

#define UI_BAT_X           90
#define UI_BAT_Y           6
#define UI_BAT_W           46
#define UI_BAT_H           18

#define UI_TITLE_CX        (SCREEN_WIDTH / 2)
#define UI_TITLE_CY        (UI_SYSTEM_BAR_H + UI_TITLE_BAR_H / 2)
#define UI_CONN_TEXT_X     20
#define UI_CONN_TEXT_Y     (UI_SYSTEM_BAR_H / 2)

#define DASH_PWR_X         190
#define DASH_PWR_Y         (UI_SYSTEM_BAR_H + 2)
#define DASH_PWR_W         42
#define DASH_PWR_H         20

#else // UI_LANDSCAPE — matches current hardcoded layout exactly

#define UI_NAV_PREV_X      248
#define UI_NAV_PREV_Y      4
#define UI_NAV_PREV_W      24
#define UI_NAV_PREV_H      24
#define UI_NAV_PAGE_CX     282
#define UI_NAV_NEXT_X      296
#define UI_NAV_NEXT_Y      4
#define UI_NAV_NEXT_W      22
#define UI_NAV_NEXT_H      24

#define UI_NAV_PREV_HIT_X0 244
#define UI_NAV_PREV_HIT_X1 280
#define UI_NAV_NEXT_HIT_X0 288
#define UI_NAV_NEXT_HIT_X1 320

#define UI_BAT_X           198
#define UI_BAT_Y           7
#define UI_BAT_W           46
#define UI_BAT_H           18

#define UI_TITLE_CX        142
#define UI_TITLE_CY        (STATUS_BAR_H / 2)
#define UI_CONN_TEXT_X     20
#define UI_CONN_TEXT_Y     (STATUS_BAR_H / 2)

#define DASH_PWR_X         148
#define DASH_PWR_Y         4
#define DASH_PWR_W         42
#define DASH_PWR_H         24

#endif

// ---------------------------------------------------------------------------
// Power confirm dialog
// ---------------------------------------------------------------------------
#if defined(UI_PORTRAIT)

#define PWR_DIALOG_X       12
#define PWR_DIALOG_Y       80
#define PWR_DIALOG_W       216
#define PWR_DIALOG_H       160
#define PWR_CANCEL_X       20
#define PWR_CONFIRM_X      124
#define PWR_BTN_Y          190
#define PWR_BTN_W          96
#define PWR_BTN_H          40
#define PWR_TITLE_CX       (SCREEN_WIDTH / 2)
#define PWR_TITLE_CY       110
#define PWR_HINT_CY        140

#else

#define PWR_DIALOG_X       28
#define PWR_DIALOG_Y       52
#define PWR_DIALOG_W       264
#define PWR_DIALOG_H       140
#define PWR_CANCEL_X       40
#define PWR_CONFIRM_X      168
#define PWR_BTN_Y          132
#define PWR_BTN_W          112
#define PWR_BTN_H          44
#define PWR_TITLE_CX       160
#define PWR_TITLE_CY       78
#define PWR_HINT_CY        108

#endif

// ---------------------------------------------------------------------------
// Macro button grid
// ---------------------------------------------------------------------------
#if defined(UI_PORTRAIT)

#define UI_GRID_BTN_W      112
#define UI_GRID_BTN_H      76
#define UI_GRID_ORIGIN_X   6
#define UI_GRID_ORIGIN_Y   (STATUS_BAR_H + 6)
#define UI_GRID_GAP_X      6
#define UI_GRID_GAP_Y      6

#define UI_WIDE_BTN_W      228
#define UI_WIDE_BTN_H      72
#define UI_WIDE_BTN_X      6
#define UI_WIDE_BTN_ORIGIN_Y (STATUS_BAR_H + 8)
#define UI_WIDE_BTN_GAP    8

#define UI_SINGLE_BTN_W    228
#define UI_SINGLE_BTN_H    48
#define UI_SINGLE_BTN_X    6
#define UI_SINGLE_BTN_Y    (STATUS_BAR_H + 4)

#else

#define UI_GRID_BTN_W      98
#define UI_GRID_BTN_H      94
#define UI_GRID_ORIGIN_X   7
#define UI_GRID_ORIGIN_Y   38
#define UI_GRID_GAP_X      6
#define UI_GRID_GAP_Y      6

#define UI_WIDE_BTN_W      300
#define UI_WIDE_BTN_H      58
#define UI_WIDE_BTN_X      10
#define UI_WIDE_BTN_ORIGIN_Y 38
#define UI_WIDE_BTN_GAP    8

#define UI_SINGLE_BTN_W    300
#define UI_SINGLE_BTN_H    42
#define UI_SINGLE_BTN_X    10
#define UI_SINGLE_BTN_Y    36

#endif

// ---------------------------------------------------------------------------
// Voice page
// ---------------------------------------------------------------------------
#if defined(UI_PORTRAIT)

#define UI_VOICE_BTN_W     228
#define UI_VOICE_BTN_H     44
#define UI_VOICE_BTN_X     6
#define UI_VOICE_BTN_Y     (STATUS_BAR_H + 4)

#define UI_VOICE_AUDIO_X   6
#define UI_VOICE_AUDIO_Y   (STATUS_BAR_H + 52)
#define UI_VOICE_AUDIO_W   110
#define UI_VOICE_AUDIO_H   36

#define UI_VOICE_CARD_X    6
#define UI_VOICE_CARD_Y    (STATUS_BAR_H + 92)
#define UI_VOICE_CARD_W    228
#define UI_VOICE_CARD_H    168

#define UI_VOICE_VP_X      10
#define UI_VOICE_VP_Y      (UI_VOICE_CARD_Y + 34)
#define UI_VOICE_VP_W      186
#define UI_VOICE_VP_H      128
#define UI_VOICE_VISIBLE_LINES 8
#define UI_VOICE_TEXT_MAX_W 182
#define UI_VOICE_LINE_H    16

#define UI_VOICE_CTRL_X    202
#define UI_VOICE_CTRL_W    26
#define UI_VOICE_SCROLL_UP_Y0   (UI_VOICE_VP_Y)
#define UI_VOICE_SCROLL_UP_Y1   (UI_VOICE_VP_Y + 34)
#define UI_VOICE_SCROLL_DN_Y0   (UI_VOICE_VP_Y + UI_VOICE_VP_H - 34)
#define UI_VOICE_SCROLL_DN_Y1   (UI_VOICE_VP_Y + UI_VOICE_VP_H)

#define UI_VOICE_CLR_X0    188
#define UI_VOICE_CLR_X1    230
#define UI_VOICE_CLR_Y0    UI_VOICE_CARD_Y
#define UI_VOICE_CLR_Y1    (UI_VOICE_CARD_Y + 30)

#define UI_VOICE_AUDIO_HIT_X0  UI_VOICE_AUDIO_X
#define UI_VOICE_AUDIO_HIT_X1  (UI_VOICE_AUDIO_X + UI_VOICE_AUDIO_W)
#define UI_VOICE_AUDIO_HIT_Y0  UI_VOICE_AUDIO_Y
#define UI_VOICE_AUDIO_HIT_Y1  (UI_VOICE_AUDIO_Y + UI_VOICE_AUDIO_H)

#define UI_VOICE_CHAT_HIT_X0   UI_VOICE_CARD_X
#define UI_VOICE_CHAT_HIT_X1   (UI_VOICE_CARD_X + UI_VOICE_CARD_W)
#define UI_VOICE_CHAT_HIT_Y0   (UI_VOICE_CARD_Y + 30)
#define UI_VOICE_CHAT_HIT_Y1   (UI_VOICE_CARD_Y + UI_VOICE_CARD_H)

#else

#define UI_VOICE_BTN_W     222
#define UI_VOICE_BTN_H     42
#define UI_VOICE_BTN_X     10
#define UI_VOICE_BTN_Y     36

#define UI_VOICE_AUDIO_X   238
#define UI_VOICE_AUDIO_Y   36
#define UI_VOICE_AUDIO_W   72
#define UI_VOICE_AUDIO_H   42

#define UI_VOICE_CARD_X    10
#define UI_VOICE_CARD_Y    82
#define UI_VOICE_CARD_W    300
#define UI_VOICE_CARD_H    152

#define UI_VOICE_VP_X      14
#define UI_VOICE_VP_Y      115
#define UI_VOICE_VP_W      262
#define UI_VOICE_VP_H      116
#define UI_VOICE_VISIBLE_LINES 7
#define UI_VOICE_TEXT_MAX_W 258
#define UI_VOICE_LINE_H    16

#define UI_VOICE_CTRL_X    280
#define UI_VOICE_CTRL_W    26
#define UI_VOICE_SCROLL_UP_Y0   114
#define UI_VOICE_SCROLL_UP_Y1   148
#define UI_VOICE_SCROLL_DN_Y0   194
#define UI_VOICE_SCROLL_DN_Y1   236

#define UI_VOICE_CLR_X0    254
#define UI_VOICE_CLR_X1    312
#define UI_VOICE_CLR_Y0    82
#define UI_VOICE_CLR_Y1    112

#define UI_VOICE_AUDIO_HIT_X0  232
#define UI_VOICE_AUDIO_HIT_X1  316
#define UI_VOICE_AUDIO_HIT_Y0  34
#define UI_VOICE_AUDIO_HIT_Y1  80

#define UI_VOICE_CHAT_HIT_X0   10
#define UI_VOICE_CHAT_HIT_X1   310
#define UI_VOICE_CHAT_HIT_Y0   112
#define UI_VOICE_CHAT_HIT_Y1   234

#endif

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
#if defined(UI_PORTRAIT)

#define UI_DASH_CARD_X     6
#define UI_DASH_CARD_Y     (STATUS_BAR_H + 4)
#define UI_DASH_CARD_W     228
#define UI_DASH_CARD_H     140

#define UI_DASH_VOL_Y      (STATUS_BAR_H + 150)
#define UI_DASH_VOL_H      34
#define UI_DASH_VOL_MINUS_X 6
#define UI_DASH_VOL_MINUS_W 40
#define UI_DASH_VOL_PLUS_X  194
#define UI_DASH_VOL_PLUS_W  40
#define UI_DASH_VOL_CTR_X   50
#define UI_DASH_VOL_CTR_W   140
#define UI_DASH_VOL_TRACK_X 58
#define UI_DASH_VOL_TRACK_W 124
#define UI_DASH_VOL_LABEL_CX 120

#define UI_DASH_ENV_Y      (STATUS_BAR_H + 190)
#define UI_DASH_ENV_H      40
#define UI_DASH_ENV_W      108
#define UI_DASH_ENV_GAP    12
#define UI_DASH_HOME_X     UI_DASH_CARD_X
#define UI_DASH_WORK_X     (UI_DASH_CARD_X + UI_DASH_ENV_W + UI_DASH_ENV_GAP)

#define UI_DASH_VOL_HIT_Y0  (UI_DASH_VOL_Y - 4)
#define UI_DASH_VOL_HIT_Y1  (UI_DASH_VOL_Y + UI_DASH_VOL_H + 4)
#define UI_DASH_VOL_DOWN_X0 2
#define UI_DASH_VOL_DOWN_X1 50
#define UI_DASH_VOL_UP_X0   190
#define UI_DASH_VOL_UP_X1   238
#define UI_DASH_VOL_MUTE_X0 50
#define UI_DASH_VOL_MUTE_X1 190

#define UI_DASH_HOME_HIT_X0 UI_DASH_HOME_X
#define UI_DASH_HOME_HIT_X1 (UI_DASH_HOME_X + UI_DASH_ENV_W)
#define UI_DASH_WORK_HIT_X0 UI_DASH_WORK_X
#define UI_DASH_WORK_HIT_X1 (UI_DASH_WORK_X + UI_DASH_ENV_W)
#define UI_DASH_ENV_HIT_Y0  UI_DASH_ENV_Y
#define UI_DASH_ENV_HIT_Y1  SCREEN_HEIGHT

#else

#define UI_DASH_CARD_X     8
#define UI_DASH_CARD_Y     34
#define UI_DASH_CARD_W     304
#define UI_DASH_CARD_H     122

#define UI_DASH_VOL_Y      158
#define UI_DASH_VOL_H      34
#define UI_DASH_VOL_MINUS_X 8
#define UI_DASH_VOL_MINUS_W 44
#define UI_DASH_VOL_PLUS_X  268
#define UI_DASH_VOL_PLUS_W  44
#define UI_DASH_VOL_CTR_X   56
#define UI_DASH_VOL_CTR_W   208
#define UI_DASH_VOL_TRACK_X 70
#define UI_DASH_VOL_TRACK_W 180
#define UI_DASH_VOL_LABEL_CX 160

#define UI_DASH_ENV_Y      196
#define UI_DASH_ENV_H      38
#define UI_DASH_ENV_W      146
#define UI_DASH_ENV_GAP    12
#define UI_DASH_HOME_X     UI_DASH_CARD_X
#define UI_DASH_WORK_X     (UI_DASH_CARD_X + UI_DASH_ENV_W + UI_DASH_ENV_GAP)

#define UI_DASH_VOL_HIT_Y0  152
#define UI_DASH_VOL_HIT_Y1  192
#define UI_DASH_VOL_DOWN_X0 4
#define UI_DASH_VOL_DOWN_X1 54
#define UI_DASH_VOL_UP_X0   266
#define UI_DASH_VOL_UP_X1   316
#define UI_DASH_VOL_MUTE_X0 55
#define UI_DASH_VOL_MUTE_X1 265

#define UI_DASH_HOME_HIT_X0 4
#define UI_DASH_HOME_HIT_X1 158
#define UI_DASH_WORK_HIT_X0 160
#define UI_DASH_WORK_HIT_X1 316
#define UI_DASH_ENV_HIT_Y0  194
#define UI_DASH_ENV_HIT_Y1  240

#endif

// ---------------------------------------------------------------------------
// Storage explorer
// ---------------------------------------------------------------------------
#if defined(UI_PORTRAIT)

#define UI_STOR_CARD_X     6
#define UI_STOR_CARD_Y     (STATUS_BAR_H + 4)
#define UI_STOR_CARD_W     228
#define UI_STOR_CARD_H     36

#define UI_STOR_NAV_Y      (STATUS_BAR_H + 44)
#define UI_STOR_NAV_H      22
#define UI_STOR_UP_X       130
#define UI_STOR_UP_W       48
#define UI_STOR_REF_X      182
#define UI_STOR_REF_W      46

#define UI_STOR_LIST_X     6
#define UI_STOR_LIST_Y     (STATUS_BAR_H + 70)
#define UI_STOR_LIST_W     228
#define UI_STOR_ROW_H      26
#define UI_STOR_VISIBLE_ROWS 6

#define UI_STOR_SCROLL_BAR_H 28
#define UI_STOR_SCROLL_Y   (SCREEN_HEIGHT - UI_STOR_SCROLL_BAR_H - 2)
#define UI_STOR_SCROLL_UP_X 6
#define UI_STOR_SCROLL_DN_X 122
#define UI_STOR_SCROLL_BTN_W 112

#define UI_STOR_UP_HIT_X0  126
#define UI_STOR_UP_HIT_X1  180
#define UI_STOR_REF_HIT_X0 178
#define UI_STOR_REF_HIT_X1 232
#define UI_STOR_NAV_HIT_Y0 UI_STOR_NAV_Y
#define UI_STOR_NAV_HIT_Y1 (UI_STOR_NAV_Y + UI_STOR_NAV_H)

#define UI_STOR_SCROLL_HIT_Y0 UI_STOR_SCROLL_Y
#define UI_STOR_SCROLL_HIT_Y1 SCREEN_HEIGHT
#define UI_STOR_SCROLL_UP_HIT_X0 UI_STOR_SCROLL_UP_X
#define UI_STOR_SCROLL_UP_HIT_X1 (UI_STOR_SCROLL_UP_X + UI_STOR_SCROLL_BTN_W)
#define UI_STOR_SCROLL_DN_HIT_X0 UI_STOR_SCROLL_DN_X
#define UI_STOR_SCROLL_DN_HIT_X1 (UI_STOR_SCROLL_DN_X + UI_STOR_SCROLL_BTN_W)

#define UI_STOR_LIST_HIT_X0 UI_STOR_LIST_X
#define UI_STOR_LIST_HIT_X1 (UI_STOR_LIST_X + UI_STOR_LIST_W)
#define UI_STOR_LIST_HIT_Y0 UI_STOR_LIST_Y
#define UI_STOR_LIST_HIT_Y1 UI_STOR_SCROLL_Y

#else

#define UI_STOR_CARD_X     8
#define UI_STOR_CARD_Y     34
#define UI_STOR_CARD_W     304
#define UI_STOR_CARD_H     36

#define UI_STOR_NAV_Y      73
#define UI_STOR_NAV_H      20
#define UI_STOR_UP_X       226
#define UI_STOR_UP_W       46
#define UI_STOR_REF_X      276
#define UI_STOR_REF_W      36

#define UI_STOR_LIST_X     8
#define UI_STOR_LIST_Y     96
#define UI_STOR_LIST_W     258
#define UI_STOR_ROW_H      27
#define UI_STOR_VISIBLE_ROWS 5

#define UI_STOR_SCROLL_X   272
#define UI_STOR_SCROLL_W   40
#define UI_STOR_SCROLL_BTN_H 65

#define UI_STOR_UP_HIT_X0  220
#define UI_STOR_UP_HIT_X1  272
#define UI_STOR_REF_HIT_X0 274
#define UI_STOR_REF_HIT_X1 316
#define UI_STOR_NAV_HIT_Y0 70
#define UI_STOR_NAV_HIT_Y1 96

#define UI_STOR_SCROLL_HIT_X0 270
#define UI_STOR_SCROLL_HIT_X1 316
#define UI_STOR_SCROLL_HIT_Y0 96
#define UI_STOR_SCROLL_HIT_Y1 238
#define UI_STOR_SCROLL_MID_Y  166

#define UI_STOR_LIST_HIT_X0 8
#define UI_STOR_LIST_HIT_X1 268
#define UI_STOR_LIST_HIT_Y0 96
#define UI_STOR_LIST_HIT_Y1 236

#endif
