# dc-taisen-netplay
A tunnel script for playing Dreamcast taisen link cable games over the internet.
Captures Dreamcast serial port communication and sends it between two instances of the script via UDP.

Features:
 * Optional matchmaking
 * Peer to peer connections
 * Basic NAT traversal

Requirements:
 * Dreamcast console and supported game(s)
 * USB "coder's cable" https://dreamcast.wiki/Coder%27s_cable
 * Python installation and this script
 * Someone to play against

Supported games:
 * Aero Dancing F (JP)
 * Aero Dancing I (JP)
 * F355 Challenge (US/JP)
 * Virtual On: Oratorio Tangram (US/JP) - region/release must match when linking
 * Hell Gate (Beta) - Works, but game is broken

Unsupported games with link mode:
 * Sega Tetris (JP) 
 
 If you want to use this with Dreampi there is a simple UI available ![here](https://github.com/eaudunord/taisen-web-ui)
