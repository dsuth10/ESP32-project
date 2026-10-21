# Making the classroom companion accessible

Product discovery and recommended direction — 21 October 2026

Status: recommendations, not an implemented release plan. Based on the current working tree, including existing uncommitted companion changes. No firmware, application behaviour, licensing or repository visibility was changed by this review. Hardware and classroom operation were not retested. Remote repository visibility could not be confirmed because the GitHub CLI could not connect.

## Product proposition

An open classroom and presentation companion: speak what you want written, put it into the document you are presenting, and ask your chosen AI agent to help configure, repair and extend the system.

Lead demonstrations with the teaching outcome: keep facing the class, dictate an explanation, ask for a clearer version, and put it on the board. The device controls the computer; writing appears in an editable application displayed by that computer. It does not independently write to every interactive board or control arbitrary presentation software.

The two valuable parts are the convenient handheld interaction and the ability to maintain a personal tool through conversation. Adoption depends on making both repeatable for someone who has never used a terminal. An open repository alone will mainly attract makers.

## What we already have

| Existing capability | Evidence | Product implication |
| --- | --- | --- |
| ES3C28P ESP32-S3 touchscreen firmware, keyboard shortcuts and enclosure sources | README.md, platformio.ini, src/macropad_config.cpp, docs/dimensions/ | Start with one supported board and tested enclosure. Avoid multiplying hardware variants initially. |
| Compose and Dictate use Bluetooth key events and the PC microphone | README.md, tools/compose/compose_companion.py | The principal writing workflow does not require device Wi-Fi, a hotspot or Hermes. |
| Companion window controls and keyboard triggers | README.md, tools/compose/compose_gui.py | Teachers can evaluate writing before acquiring hardware. Packaging this as an accessible trial is still work. |
| Local Whisper/Ollama and configured cloud speech/writing | tools/compose/speech_pipeline.py, llm_pipeline.py, compose.env.example | Offer explicit processing choices and benchmark ordinary laptops. Local processing is not automatically fast or preinstalled. |
| Held results when focus changes, followed by Paste Ready | README.md, clipboard_manager.py | Preserve this protection and explain where the result will go. Test each supported target app. |
| Separate device-microphone voice receiver with Hermes and other backend routes | server/hermes_voice_receiver.py, receiver.env.example | Keep this as an advanced capability; backend routing differs from Compose. |
| Home/work selection and cached discovered addresses persist | src/environment_manager.cpp | Preserve portability, but initial network credentials/endpoints still originate in compile-time configuration. This is not general runtime provisioning. |
| New local companion code starts the voice receiver automatically | tools/compose/compose_gui.py, receiver_service.py | A simple writing installation should be able to leave the optional receiver off. Current launch coupling needs deliberate redesign. |

There is no standard end-user agent management interface established by this review. Today an agent works through the repository, tools and access available on the user's computer. That is a useful development method, but needs packaging before it becomes a repeatable product promise.

## Three entry points, one project

1. **Try the writing software.** Windows companion, on-screen controls and keyboard shortcuts. No device purchase. Test with the teacher's usual microphone and editable document. Include a demonstration with synthetic text and a clear route to local or school-approved processing.
2. **Add the handheld remote.** Preconfigured firmware, pair Bluetooth, choose microphone, test Dictate, Compose and Paste Ready. Use a simple default screen with those controls and a few presentation shortcuts. Retain other pages behind an advanced setting. The physical remote is the benefit to evaluate: can the teacher keep moving and teaching?
3. **Connect a personal agent and additional locations.** Optional Hermes, device microphone, audio replies, network profiles and specialist automations. Keep the existing owner's setup as an explicit advanced configuration with regression tests.

Agent-assisted setup and support should be available at every entry point. A long-running Hermes installation should not be necessary merely to use Dictate. Nor should daily writing fail because a maintenance agent is unavailable.

## Make agent management a real feature

Separate the agent that produces classroom text from the agent that maintains the system. Teachers may choose different providers for these jobs. A chat endpoint that writes text does not necessarily have access to restart a service or flash a board.

Build a small local management layer, initially usable through a CLI with structured JSON. Candidate operations: status, microphone test, Bluetooth event test, processing test, configuration validation, companion restart, diagnostic export, update and rollback. These names describe proposed operations, not commands that exist today. An optional MCP adapter can follow once the operations are stable.

Ship versioned agent instructions describing the board, component boundaries, supported commands, known failure categories and required verification. Maintain an explicit capability table for each supported agent: chat only; local diagnostics/configuration; source modification/build/upload. A hosted chat session cannot automatically see a local USB device or repair a phone setting.

For common requests such as changing a button label, shortcut, microphone or provider, use validated configuration rather than source changes. For genuinely new features, preserve the conversational development model: agent makes an isolated change, builds/tests it, offers a recoverable installation, and verifies the result. Keep personal customisations separate from upstream defaults so updates do not erase them.

Make the support exchange concrete: “It is not connecting” should cause separate checks of Bluetooth, companion, microphone, processing backend and optional Wi-Fi receiver. Tell the teacher what failed and what was repaired. A port accepting a connection is not proof the correct authenticated receiver or model is ready.

Diagnostics should omit document contents, recordings, transcripts, selected text, credentials and identifying network data by default. The current companion logs selected-text excerpts and spoken prompts; review those logging paths before enabling diagnostic sharing. Firmware builds made with private network configuration must also be excluded from public release assets.

Offer a maintained baseline and recovery path. AI assistance does not guarantee every requested extension will be feasible, correct or supportable. Human acceptance remains necessary for physical device behaviour and writing into the actual target application.

## Simplify connectivity

For the first writing release, use the existing Bluetooth-to-PC path. Cloud processing, if selected, uses the computer's connection. Moving that computer between home and school then does not require changing device Wi-Fi for the core workflow. Bluetooth pairing and microphone availability still need testing after moves; changing computers may require pairing again.

For advanced voice, add a setup wizard that writes network profiles at runtime, pairs the device with its intended receiver, and keeps each network, receiver and authentication configuration together. Existing discovery is helpful but not trusted pairing; it currently accepts receiver advertisements and uses HTTP endpoints. Define authenticated pairing and an appropriate protected transport before widening deployment. School client isolation can prevent discovery or communication even when both devices have Wi-Fi.

USB control is a useful possible fallback where Bluetooth is unavailable. The S3 has USB capabilities, but a user-facing USB control/management mode on this board still needs firmware, connector verification and testing. Do not advertise it as already supported.

The chip supports 2.4 GHz Wi-Fi. WPA2-Personal is recorded in this project's engineering notes as a hotspot workaround. Treat it as a diagnosis for a particular configuration, not proof that all ESP32-S3 systems lack WPA3. A school may require settings the user cannot change. The product should not depend on weakening or bypassing school controls. [Espressif ESP32-S3 overview](https://www.espressif.com/products/socs/esp32-s3).

Browser flashing can reduce maker setup, but does not install the Windows companion, make school USB policy disappear, or provide runtime Wi-Fi configuration without firmware support. Validate the actual board, browser and driver path before choosing it as the default.

## Licensing recommendation

Use **MIT for original firmware and companion code**. It permits use, modification, redistribution and commercial sale, subject to retaining the required notices. It does not require downstream improvements to be published. That fits the stated wish for people to adjust the project freely. [MIT licence](https://opensource.org/license/mit).

Apache-2.0 is a reasonable alternative if an explicit contributor patent grant is a priority; it has more detailed redistribution conditions. Select one rather than adding multiple software licences without a reason. [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).

Use **CERN-OHL-P-2.0 for original enclosure/hardware design files** and **CC BY 4.0 for original guides and diagrams**, with a directory/file licence map. Publish editable design sources as well as printable exports. Preserve third-party terms and distinguish manufacturer reference assets from original designs. [CERN OHL guidance](https://ohwr.org/licences/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

There is a choice behind “free for everybody”: permissive licensing lets someone charge for a modified version or keep their modifications closed. Your version can remain freely available. If you want distributed derivatives to remain open, consider GPL software and reciprocal CERN OHL variants instead. Commercial use is still compatible with copyleft. A non-commercial restriction would conflict with unrestricted reuse and prevent some useful manufacturing/distribution partnerships. [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html).

Before applying licences, establish ownership/contributor permissions and identify any relevant employment IP terms. Resolve unclear licence/provenance in bundled ESP32-BLE-Keyboard and FT6336 drivers. Preserve TFT_eSPI/NeoPixel and other dependency obligations, audit the resolved binary dependency set, and review model and manufacturer-asset rights. Missing local notices are an unresolved provenance issue, not a definitive finding that no permission exists anywhere. See [the licensing research](research/2026-10-21-licensing-research.md).

Free source does not mean free hardware, unlimited hosted inference, an AI-agent subscription or unlimited support. Explain these costs plainly. Keep a genuinely usable local option after initial model installation, with measured system requirements. Optional paid assembly, training, hosting or support can subsidise access while the source remains open.

## Accessibility and school adoption

Start with Windows because that is where the current companion works. Document the actual supported version and applications. Explore macOS/Chromebook only after testing demand and feasibility; existing Win32 paste, UI Automation and hotkey code is not portable unchanged.

Provide keyboard-only controls, readable scaling, large touch targets, high contrast, text labels alongside colour, clear recording feedback, cancel/stop, and screen-reader testing of the companion. Keep typing available as an alternative to speech. Evaluate one-handed use, different voices, classroom noise and accidental microphone activation with real users. These are proposed acceptance criteria, not current accessibility certification.

Provide a school IT sheet: installation scope, Bluetooth/USB needs, microphone permission, external endpoints, local storage and logging, network listeners, update policy and uninstall instructions. A per-user installation may reduce friction but cannot bypass device-management restrictions. Make network receiver installation optional.

Default classroom demonstrations to teacher-created, non-identifying content. Show whether processing is local or cloud and disable all external routes in a tested local mode, including search, routing, optional mirroring and maintenance-agent exports. Existing Compose local-only handling is useful; verify every separate receiver and support path before making a system-wide privacy claim. Australian privacy guidance recommends avoiding personal, especially sensitive, information in publicly available generative AI tools; schools also have jurisdiction and employer requirements. [OAIC guidance](https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/guidance-on-privacy-and-the-use-of-commercially-available-ai-products), [Australian schools AI framework](https://www.education.gov.au/schooling/resources/australian-framework-generative-artificial-intelligence-ai-schools).

## Getting it into teachers' hands

Windows already offers voice typing. Test whether the remote, composition workflow and agent customisation deliver enough additional value in a lesson. Compare against the tools teachers already use, including Windows voice typing; do not assume dictation alone creates demand. [Microsoft voice typing](https://support.microsoft.com/en-us/accessibility/windows/use-voice-typing-to-talk-instead-of-type-on-your-pc).

Publish a short real-classroom-style demonstration using synthetic material: dictate a sentence, compose an explanation, simplify highlighted text, recover a queued result. End with an immediate software trial and an optional remote kit. Offer separate teacher, maker and school-IT guides.

Start with a small teacher cohort across at least two school settings. Recruit through colleagues and professional networks, offer loan devices, and observe setup without taking over. Include teachers who are not interested in coding. Share permissioned teacher stories only after reliable use. Later distribution channels can include professional learning sessions, subject associations, makerspaces and assembly partners.

For hardware, provide a versioned bill of materials, tested purchase specification, editable enclosure sources and assembly/test instructions. Measure landed cost in AUD including enclosure, cable, delivery and assembly. Compare DIY kits, a small preassembled batch and loan devices. Do not commission custom electronics before the existing board proves demand. Selling assembled devices needs its own product-safety, battery and applicable compliance review; open licensing alone does not establish that readiness.

Sustainability needs named maintainers, a supported release, pinned build dependencies, a changelog, security reporting, contribution guidance and a bounded support policy. Turn recurring agent fixes into shared diagnostics and regression checks. Donations, grants and paid assembly/support are possible funding hypotheses to test, not assumed revenue.

## Proposed sequence and evidence gates

| Stage | Deliverable | Evidence before expanding |
| --- | --- | --- |
| 1. Establish a reusable baseline | Resolve rights gaps; sanitise templates and release inputs; preserve personal profile; choose licences; document supported hardware | Another developer can reproduce a generic build without private configuration; notices and release contents reviewed |
| 2. Package the first teacher experience | Windows installer, microphone/processing wizard, software trial, three main controls, receiver optional | Five unfamiliar teachers attempt setup; proposed target: at least four reach first successful insertion within 15 minutes without terminal use or developer takeover |
| 3. Package agent support | Structured diagnostics, configuration operations, recovery, agent instructions and tested adapters | Seed missing companion, wrong microphone, unavailable model and Bluetooth faults; agent diagnoses each within its actual permissions and records a verified outcome |
| 4. Pilot classroom use | Suggested 10–15 teachers across at least two settings, loan remotes and school IT sheet | Repeated lesson use, setup/reconnection time, task success, writing latency on ordinary laptops, teacher corrections, support minutes and continued voluntary use |
| 5. Broaden distribution | Public stable release, demonstrations, reproducible kit/assembled option and community processes | Pilot issues resolved, support load sustainable, supply cost measured, clean install/update/uninstall and recovery checked |

Numbers above are proposed experiment sizes and targets, not measured results or delivery estimates. Count downloads only as interest. Continued use without developer intervention is the stronger adoption signal.

The next implementation brief should be a bounded **teacher starter release**: preserve existing advanced functionality, make the receiver optional, provide generic runtime configuration, package the companion and establish privacy-preserving diagnostics. Agree the licence scope and resolve driver provenance before presenting a fully cleared public distribution.
