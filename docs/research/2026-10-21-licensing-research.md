# Licensing recommendation for the ESP32 classroom companion

Research date: 21 October 2026. This is a practical licensing review, not legal advice. It is based on the repository files visible on this date; it is not a complete source-code provenance or dependency audit.

## Recommendation

The stated goal — allow anyone to use, change, share, and sell the project, without requiring downstream changes to stay open — points to permissive licensing. Use a separate, purpose-fit licence for each category:

| Material | Suggested licence | Effect |
| --- | --- | --- |
| Original firmware and Python companion code | MIT, or Apache-2.0 if an express patent grant and patent-litigation termination clause are desired | Both allow commercial use, modification and redistribution with conditions. MIT mainly requires retaining copyright and licence notices. Apache-2.0 adds conditions and patent terms. |
| Original schematics, PCB/design source and enclosure CAD | CERN-OHL-P-2.0 | Purpose-built permissive open-hardware licence. Allows commercial use and adaptations subject to its notice and source requirements. |
| Original tutorials, build guides, diagrams and other explanatory content | CC BY 4.0 | Allows commercial sharing and adaptation with attribution, a licence link and indication of changes. |

Use the full canonical licence text and identify the copyright holders and year. Add a clear file-level or directory-level notice so it is obvious which licence covers which material. A repository-wide `LICENSE` alone can be ambiguous when it contains firmware, CAD, documents and third-party code. Keep third-party notices intact and list exceptions in a `THIRD_PARTY_NOTICES` file or equivalent.

The permissive choice best matches “any way” and commercial redistribution. If the owner instead wants distributed adaptations to remain open, choose copyleft deliberately: GPL-3.0-or-later for software, or CERN-OHL-W-2.0 / CERN-OHL-S-2.0 for hardware. Copyleft allows commercial sale; it adds reciprocal source/licensing obligations when covered modified works are conveyed. Strong reciprocal hardware licensing can cover modified designs and products based on them. These are distinct policy choices, not simply stronger versions of MIT.

## Repository findings and release blockers

- No root `LICENSE`, `LICENCE`, `COPYING` or `NOTICE` file was found, and no top-level project licence is declared. GitHub documents that absent a licence, default copyright applies; the repository being public does not itself grant reuse rights.
- `lib/ESP32-BLE-Keyboard/` contains source and `library.properties` but no licence file or clear licence grant in its README. The upstream repository listing likewise did not show a licence file in the inspected tree. Do not assume that attribution or availability is permission to redistribute. Establish the exact upstream code provenance and obtain a licence grant, or replace/remove this code, before publishing a blanket project licence or redistributing firmware containing it.
- `lib/FT6336/` and `libraries/FT6336/` contain local driver copies but no evident licence or provenance notice in the inspected files. Confirm origin and applicable terms for each copy; get permission or replace them if needed. This is also a blocker to confidently licensing the complete source tree and firmware.
- The bundled `lib/TFT_eSPI/license.txt` contains several historical licence texts, including LGPL 3.0 and BSD-style terms. Preserve its file and inspect which files or portions actually apply before redistributing compiled firmware. `lib/Adafruit_NeoPixel/COPYING` contains LGPL 3.0. These are not automatically incompatible with a permissive licence on original project code, but their own notices and applicable source/linking obligations continue to apply. Do not present the entire repository as MIT-only.
- `esp-idf-lvgl/components/lvgl/LICENCE.txt` and `components/lvgl_esp32_drivers/LICENSE` identify MIT. `esp-idf-lvgl/` appears to be a separate reference/demo project; confirm whether it is part of the intended release and preserve its notices if redistributed.
- Python requirements are open-ended lower bounds, not a pinned lockfile. They name sounddevice, pystray, uiautomation, pywin32, faster-whisper, requests, groq, Pillow, NumPy and SciPy; their licences and transitive dependencies need checking against the resolved release environment. Do not infer the final third-party notice set from the manifest alone.
- Models and services have their own terms. `faster-whisper` is inference software; the downloaded Whisper model or any replacement model has a separate licence. Ollama itself does not set the licence for every model served through it. Groq and Brave Search are hosted services with terms that govern account/API use. Avoid bundling models or treating software licences as permission to redistribute model weights or use a service commercially.
- Enclosure renders, board STEP/drawing/specification files, photos and other reference assets need a provenance and rights check. The ES3C28P manufacturer materials are not necessarily covered by a licence applied to original project CAD. Likewise, preserve product names and logos as marks; a copyright licence does not grant trademark endorsement rights.

The firm blockers from this quick inspection are the BLE Keyboard and FT6336 licensing/provenance gaps. The resolved Python environment, complete embedded-library notices, model terms and manufacturer/reference assets remain an audit list before a binary or full-source release is described as cleared for unrestricted redistribution.

## Licence distinctions and sources

- The OSI describes open-source licences as allowing free use, modification and sharing. Its canonical MIT text expressly includes selling copies, subject to retaining the copyright and permission notices: [OSI: MIT License](https://opensource.org/license/mit) and [OSI approved licences](https://opensource.org/licenses).
- Apache-2.0 is another permissive software option with an express patent licence and patent-litigation termination provision; see the [Apache License 2.0 text](https://www.apache.org/licenses/LICENSE-2.0).
- GNU's FAQ confirms GPL permits charging for copies, while recipients retain redistribution and modification freedoms under the GPL terms; distributed combined/modified works can carry source and licence obligations. See [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html) and the [GPLv3 text](https://www.gnu.org/licenses/gpl-3.0.html).
- CERN's hardware guidance explicitly recommends choosing a suitable licence for each kind of project material and offers permissive, weakly reciprocal and strongly reciprocal CERN OHL v2 variants. See [CERN Open Hardware Repository licences](https://ohwr.org/licences/); the page links the full text of each variant.
- CC BY 4.0 permits commercial sharing and adaptation with attribution, a licence link and change marking: [Creative Commons CC BY 4.0 deed](https://creativecommons.org/licenses/by/4.0/). Creative Commons advises against applying CC licences to software or hardware and recommends software-specific licences for code: [Creative Commons FAQ](https://creativecommons.org/faq/).
- GitHub's licensing guidance says that without a licence, default copyright applies and others may not reproduce, distribute or create derivative works: [GitHub Docs: Licensing a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
- Inspected upstream/vendor materials: [T-vK ESP32-BLE-Keyboard](https://github.com/T-vK/ESP32-BLE-Keyboard), [Bodmer TFT_eSPI](https://github.com/Bodmer/TFT_eSPI), [Adafruit NeoPixel](https://github.com/adafruit/Adafruit_NeoPixel), and [LVGL](https://github.com/lvgl/lvgl).
