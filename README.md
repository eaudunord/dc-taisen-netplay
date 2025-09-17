# dc-taisen-netplay
A tunnel script for playing Dreamcast taisen link cable games over the internet.
Captures Dreamcast serial port communication and sends it between two instances of the script via UDP.

Features:
 * Optional matchmaking
 * Peer to peer connections
 * Basic NAT traversal

Requirements:
 * Dreamcast console and supported game(s)
 * USB serial adapter. See below for more info
 * Python installation and this script
 * Someone to play against

Supported games:
 * Aero Dancing F (JP)
 * Aero Dancing I (JP)
 * F355 Challenge (US/JP)
 * Virtual On: Oratorio Tangram (US/JP) - region/release must match when linking
 * Maximum Speed (Atomiswave to Dreamcast conversion)
 * Hell Gate (Beta) - Works, but game is broken

Unsupported games with link mode:
 * Sega Tetris (JP) 
 
 If you want to use this with Dreampi there is a simple UI available https://github.com/eaudunord/taisen-web-ui
 
 The easiest way to get up and running hardware-wise would be to acquire the following:
 * Dreamcast SD Adapter
 * SD card sniffer (micro or full size)
 * USB to TTL serial adapter with a *cp2102n* chipset. This is the most reliable chip I've tested so far
 ![Screenshot](https://github.com/eaudunord/dc-taisen-netplay/blob/main/Materials.jpg?raw=true)
 
 Assembly:
 * Attach header row pins to the SD sniffer. Solderless press fit, or friction fit options are available if you can't solder.
 * Connect the appropriate wires from the USB-serial adapter to the corresponding pins using the chart below as a guide
 * Insert the SD card sniffer fully into the SD card slot on the SD adapter
 * Insert the SD adapter into the Serial port on the Dreamcast console
 ![Screenshot](https://github.com/eaudunord/dc-taisen-netplay/blob/main/ConnectionGuide.PNG?raw=true)