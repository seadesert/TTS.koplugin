# TTS plugin for Koreader (Kindle version)

Adds text to speech capabilities using [KinAMP](https://github.com/kbarni/KinAMP) and [piper](https://github.com/OHF-Voice/piper1-gpl/) as a backend
This fork focuses support for Kindle devices (play audio on headphones connected to Kindle via Bluetooth)


## Pre-requisites

1. Kindle with KinAMP and Koreader installed
2. A PC to host piper-tts web server


## Installation

1. Install [piper](https://github.com/OHF-Voice/piper1-gpl/) on any device within your network using `pip install piper-tts>=1.3.0`  
   I tried getting piper to work on my kindle, but did not succed, so I instead run it on my computer and connect to it via my local WiFi.
   It could in theory run on a phone in Termux, but the package is broken there right now
2. Download a piper voice and try it out [with this guide](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_HTTP.md)
3. Set up the piper web server [with this guide](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_HTTP.md)
4. Download this repo
5. Change the `play` file to be able to play audio files on your target device.
   The default one uses the [KinAMP](https://github.com/kbarni/KinAMP), so install it if you're on Kindle
6. Change the `stop_playing` file be able to interrupt playback. Again, the default file is made for sox on kindle
7. Drop the entire TTS.koplugin directory into koreader/plugins on your device


# Issues with Kindle Bluetooth on Koreader

Unfortunately currently there is no bluetooth control from Koreader (as the com.lab126.btfd service is disabled) - so probably the headphone will disconnect after 20 minutes.

Workaround: Running [KinAMP](https://github.com/kbarni/KinAMP) in background mode (run KinAMP from Kindle Homepage and start background playback) seems to keeps the headphones from getting disconnected. (Need more analysis to confirm workaround and arive at fix)


## Steps to use

1. Connect your bluetooth headphone on Kindle menu
2. Launch KinAMP in background mode (optional, to prevent frequent disconnects)
3. Run koreader and open a book
4. Open koreader, open a book, click on "Start TTS mode" in the typesetting menu
5. For first time setup, click on "TTS server URL" and input the IP address of the piper TTS web server
6. Click on play button to start

## Scripts

the `play` is invoked with the file name to play as the first argument and the volume as the second argument.
The plugin thinks the playback is finished when the script outputs any charachter,
so make sure to `>/dev/null 2>/dev/null` anything that can output text and add an `echo` at the end

the `stop_playing` is run to interrupt playback, so it should kill the program you used in the `play` script

the `on_tts_start` script is run when you click the "Start TTS mode" button in koreader.
You can put stuff like connecting to bluetooth headphones there
