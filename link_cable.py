#link_version=2025.09.06.1345

import socket
import time
import serial
import select
import sys
import threading
import logging
import os
import requests
import binascii
import subprocess
import errno
try:
    import stun
except ImportError:
    os.system('pip install pystun3')
    import stun

if sys.version_info < (3,0,0):
    input = raw_input

class taisenLink():
    osName = os.name
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('Tunnel')
    logger.setLevel(logging.INFO)
    packetSplit = b"<packetSplit>"
    dataSplit = b"<dataSplit>"

    def __init__(self, pinging = True, ping_rate = 3, printout = False):
        # self.ping = time.time()
        self.pinging = pinging
        self.ping_rate = ping_rate
        self.printout = printout
        self.com_port = None
        self.game = None
        self.baud = None
        self.ms = None
        self.dial_string = None
        self.matching = None
        self.VOOT_sync = None
        self.udp = None
        self.ser = None
        self.alt_timeout = 0.01
        self.ftdi_latency = 1
        self.state = "starting"
        self.my_ip = None
        self.ext_port = None

    def setup(self):
        opponent = None
        for arg in sys.argv[1:]:
            if len(arg.split("=")[1].strip()) == 0:
                continue
            elif arg.split("=")[0] == "com":
                self.com_port = arg.split("=")[1].strip()
            elif arg.split("=")[0] == "game":
                self.game = arg.split("=")[1].strip()
            elif arg.split("=")[0] == "state":
                self.ms = arg.split("=")[1].strip()
            elif arg.split("=")[0] == "address":
                self.dial_string = arg.split("=")[1].strip()
            elif arg.split("=")[0] == "baud":
                self.baud = int(arg.split("=")[1].strip())
            elif arg.split("=")[0] == "matching":
                self.matching = arg.split("=")[1].strip()
            elif arg.split("=")[0] == "ftdi":
                self.ftdi_latency = int(arg.split("=")[1].strip())
        
        if self.dial_string and self.ms:
            if self.ms == 'calling':
                opponent = (self.dial_string, 21001)                     
        
        while True:
            if not self.com_port:
                self.com_port = input("\nCOM port: ")
                if "COM" in self.com_port.upper():
                    self.com_port = self.com_port.upper()
                if self.com_port.startswith("tty"):
                    self.com_port = "/dev/" + self.com_port
                try:
                    int(self.com_port)
                    self.com_port = "COM" + self.com_port
                except ValueError:
                    pass
            try:
                self.logger.info("Trying " + str(self.com_port))
                testCon = serial.Serial(self.com_port, 9600, exclusive=True )
                testCon.close()
                break
            except serial.SerialException as e:
                if "FileNotFoundError" in str(e.args[0]):
                    self.logger.info("Invalid COM port")
                    self.com_port = None
                    continue
                elif "PermissionError" in str(e.args[0]):
                    self.logger.info("COM port in use")
                    self.com_port = None
                    continue
                elif e.args[0] == 2:
                    self.logger.info("Invalid COM port")
                    self.com_port = None
                    continue
                elif e.args[0] == 11:
                    self.logger.info("Port in use. Try stopping Dreampi service")
                    return
                else:
                    self.logger.info(e)
                    self.com_port = None
                    continue

        self.logger.info("Using %s" % self.com_port)

        while True:
            
            if self.game == '1':
                self.baud = 28800
            elif self.game == '2':
                self.baud = 38400
            elif self.game == '3':
                self.baud = 223214
            elif self.game == '4':
                self.baud = 115200
            elif self.game == '5':
                self.baud = 260416
            elif self.game == '6':
                self.baud = 57600
            elif self.game == '7':
                try:
                    self.baud = int(input("\ncustom baud: "))
                    int(self.baud)
                except ValueError:
                    self.logger.info("Invalid selection")
                    self.game = None
                    self.baud = None
                    continue
            elif self.game == '8':
                try:
                    multiplier = int(input("\nSCBRR2 multiplier: "))
                    int(multiplier)
                    self.baud = int(round((50*1000000)/(multiplier+1)/32,0))
                    self.logger.info(self.baud)
                except ValueError:
                    self.logger.info("Invalid selection")
                    self.game = None
                    self.baud = None
                    continue
            elif self.game == '9':
                self.baud = 223214
            else:
                # self.logger.info("invalid selection")
                self.game = None
                
            if self.game:
                break
            self.game = input("\nGame:\r\n[1] Aero Dancing F\r\n[2] Aero Dancing I\r\n[3] F355\r\n[4] Sega Tetris\r\n[5] Virtual On\r\n[6] Hell Gate\r\n[7] custom\r\n[8] calculated\r\n[9] Maximum Speed\r\n"
                )
            continue



        if not self.dial_string:
            while True:
                if self.matching == "2":
                    self.dial_string = input("Opponent IP address: ")
                elif self.matching == "1":
                    self.dial_string = "3" + str(self.game)
                    my_ip, ext_port = self.getWanIP(21002)
                    if my_ip and ext_port:
                        self.my_ip = my_ip
                        self.ext_port = ext_port
                    # self.logger.info("My info: " + str((my_ip, ext_port)))
                    if self.my_ip:
                        # time.sleep(3)
                        status, opponent = self.get_match(self.dial_string[-2:], self.my_ip, self.ext_port)
                        if status:
                            # self.logger.info(opponent)
                            self.ms = "calling"
                        else:
                            if self.udp:
                                self.close_udp()
                                time.sleep(3)
                            self.ms = "waiting"
                    else:
                        self.ms = None
                        self.logger.info("Error getting WAN info.")
                        continue
                else:
                    self.matching = None
                if self.matching:
                    break
                self.matching = input("[1] Use matchmaking server\r\n[2] Enter IP Address\r\n")
                
        while True:
            if self.ms:
                break
            side = input('\nWait or connect:\n[1] Wait\n[2] Connect\n')
            if side == '1' or side =='2':
                if side == '1':
                    self.ms = "waiting"
                else:
                    self.ms = "calling"
                    opponent = (self.dial_string, 21001)
            else:
                self.logger.info('Invalid selection')
                self.ms = None
                continue

        self.logger.info("setting serial rate to: %s" % self.baud)
        self.ser = serial.Serial(self.com_port, baudrate=self.baud, rtscts=True, exclusive=True)
        self.ser.reset_output_buffer() #flush the serial output buffer. It should be empty, but doesn't hurt.
        self.ser.reset_input_buffer()
        self.ser.timeout = None
        if self.osName == "posix":
            try:
                command_str = "sudo bash -c 'echo %s > /sys/bus/usb-serial/devices/%s/latency_timer'" % (self.ftdi_latency, self.com_port.split("/")[-1])
                subprocess.check_output([command_str], shell=True)
                self.logger.info("FTDI latency set to %s" % self.ftdi_latency)
            except:
                self.logger.info("Ok. Skipping latency timer")
                pass
            pass
        variables = (
            self.ms,
            opponent
        )
        return variables

    def initConnection(self):
        self.my_ip = None
        self.ext_port = None
        if len(self.dial_string) > 2:
            opponent = self.dial_string.replace('*','.')
            ip_set = opponent.split('.')
            for i,set in enumerate(ip_set): #socket connect doesn't like leading zeroes now
                fixed = str(int(set))
                ip_set[i] = fixed
            if self.ms == "waiting":
                oppPort = 21002
            else:
                oppPort = 21001
            opponent = (('.').join(ip_set), oppPort)
            return ("connecting",opponent)

        elif len(self.dial_string) == 2:
            if self.ms == "waiting":
                registered = False
                timerStart = time.time()
                while True:
                    if time.time() - timerStart > 240:
                        if self.udp:
                            self.close_udp()
                        return ["failed", None]
                        
                    my_ip, ext_port = self.getWanIP(21001)
                    if my_ip and ext_port:
                        self.my_ip = my_ip
                        self.ext_port = ext_port
                    # self.logger.info("My info: " + str((my_ip, ext_port)))
                    if self.my_ip:
                        if not registered:
                            if self.register(self.dial_string[-2:], self.my_ip, self.ext_port):
                                registered = True
                        elif registered:
                            status, opponent = self.get_status(self.dial_string[-2:], self.my_ip)
                            if status:
                                self.logger.info("found opponent")
                                # self.logger.info(opponent)
                                # time.sleep(3)
                                return ["connecting",opponent]
                    else:
                        self.logger.info("Couldn't get WAN information. Won't register for match. Trying again in 3 seconds")
                    time.sleep(self.ping_rate)


            
        return ["failed", None]

    def listener(self, opponent):
        ping = time.time()
        lastPing = 0
        pong = time.time()
        startup = time.time()
        jitterStore = []
        pingStore = []
        currentSequence = 0
        maxPing = 0
        maxJitter = 0
        recoveredCount = 0
        established = False
        while(self.state != "netlink_disconnected"):
            if time.time() - ping >= self.ping_rate:
                try:
                    if select.select([],[self.udp],[],0)[1]:
                        self.udp.sendto(b'PING_SHIRO', opponent)
                        # self.logger.info("Sent Ping to: "+str(opponent))
                        ping = time.time()
                except ConnectionResetError:
                    # self.logger.info("Opponent Unreachable")
                    pass
            ready = select.select([self.udp],[],[],0) #polling select
            if ready[0]:
                try:
                    packetSet = self.udp.recv(1024)
                    # while time.time() - startup < 3:
                    #     # Discard packets for 3 seconds in case there are any in the OS buffer.
                    #     continue
                    #start pinging code block
                    # if pinging == True:
                    if packetSet == b'PING_SHIRO':
                        # self.logger.info("Received Ping")
                        self.udp.sendto(b'PONG_SHIRO', opponent)
                        continue
                    elif packetSet == b'RESET_COUNT_SHIRO':
                        # If peer reset their tunnel, we need to reset our sequence counter.
                        self.logger.info("Packet sequence reset")
                        currentSequence = 0
                        self.udp.sendto(b'START', opponent)
                        continue
                    elif packetSet == b'START':
                        self.logger.info("Connection established. Begin link play")
                        established = True
                    elif b'VOOT_SYNC' in packetSet:
                        self.logger.info("\r\nVOOT connection attempt. Choose " + packetSet.split(b'VOOT_SYNC')[2].decode() )
                        self.VOOT_sync = packetSet.split(b'VOOT_SYNC')[1]
                        # self.logger.info(self.VOOT_sync)
                        continue
                    elif packetSet == b'VOOT_RESET':
                        self.logger.info("VOOT synced")
                        self.VOOT_sync = None
                        continue
                    elif packetSet == b'PONG_SHIRO':
                        # self.logger.info("Received Pong")
                        if not established:
                            # self.logger.info("Sending Reset")
                            self.udp.sendto(b'RESET_COUNT_SHIRO', opponent) 
                            # we know there's a peer because it responded to our ping
                            # tell it to reset its sequence counter
                            # first_run = False
                        pong = time.time()
                        pingResult = round((pong-ping)*1000,2)
                        if pingResult > 500:
                            continue
                        if pingResult > maxPing:
                            maxPing = pingResult
                        pingStore.insert(0,pingResult)
                        if len(pingStore) > 20:
                            pingStore.pop()
                        jitter = round(abs(pingResult-lastPing),2)
                        if jitter > maxJitter:
                            maxJitter = jitter
                        jitterStore.insert(0,jitter)
                        if len(jitterStore) >20:
                            jitterStore.pop()
                        jitterAvg = round(sum(jitterStore)/len(jitterStore),2)
                        pingAvg = round(sum(pingStore)/len(pingStore),2)
                        if self.osName != 'posix' and self.pinging == True:
                            sys.stdout.write('Ping: %s Max: %s | Jitter: %s Max: %s | Avg Ping: %s |  Avg Jitter: %s | Recovered Packets: %s         \r' % (pingResult,maxPing,jitter, maxJitter,pingAvg,jitterAvg,recoveredCount))
                        lastPing = pingResult
                        continue
                    #end pinging code block

                    packets= packetSet.split(self.packetSplit)
                    try:
                        while True:
                            packetNum = 0
                            
                            #go through all packets 
                            for p in packets:
                                if int(p.split(self.dataSplit)[1]) == currentSequence:
                                    break
                                packetNum += 1
                                
                            #if the packet needed is not here,  grab the latest in the set
                            if packetNum == len(packets):
                                packetNum = 0
                            if packetNum > 0 :
                                recoveredCount += 1
                            message = packets[packetNum]
                            payload = message.split(self.dataSplit)[0]
                            sequence = message.split(self.dataSplit)[1]
                            if int(sequence) < currentSequence:
                                break  #All packets are old data, so drop it entirely
                            currentSequence = int(sequence) + 1
                            toSend = payload
                            # self.logger.info(binascii.hexlify(payload))
                            if self.printout:
                                self.logger.info(b'net received: '+ toSend)
                            # self.logger.info(b'net received: '+ toSend)
                            # if self.game == '4':
                            #     self.ser.send_break(0.001)
                            if self.game == '4' and self.ser.break_condition:
                                self.ser.break_condition = False
                            self.ser.write(toSend)
                            if self.game == '4':
                                self.ser.break_condition = True
                            if packetNum == 0: # if the first packet was the processed packet,  no need to go through the rest
                                break

                    except IndexError:
                        continue
                except ConnectionResetError:
                    continue
                    
        self.logger.info("listener stopped")        
                
    def sender(self, opponent):
        sequence = 0
        packets = []
        first_run = True
        VOOT = False
        syncing = False
        sync = 0
        oppside = b''
        to_read = 0

        if self.game == '5':
            self.ser.timeout = self.alt_timeout
        if self.game == '4':
            self.ser.timeout = self.alt_timeout
        
        while(self.state != "netlink_disconnected"):
            # if time.time() - ping >= ping_rate:
            #     try:
            #         self.udp.sendto(b'PING_SHIRO', opponent)
            #         self.logger.info("Sent Ping to: "+str(opponent))
            #     except ConnectionResetError:
            #         self.logger.info("Opponent Unreachable")
            #         pass
            #     ping = time.time()
            raw_input = b''

            if self.game == '5':
                to_read = 14
            elif self.game == '4':
                to_read = 17
            else:
                to_read = self.ser.in_waiting
            if to_read > 0:
                # self.logger.info(ser.in_waiting)
                raw_input += self.ser.read(to_read)
                if self.game =='4':
                    raw_input = raw_input[:16]
                    # raw_input = raw_input
            # raw_input += self.ser.read(14)
            # if len(raw_input) > 0 and self.printout:
            # if len(raw_input) > 0:
            #     self.logger.info(b'serial read: '+ raw_input)
            
            try:
                if len(raw_input) > 0:
                    # VOOT has a very finicky handshake and spoofing most of it makes things much easier.
                    if not VOOT and self.game == '5':
                        
                        if raw_input in (b'SCIXB START'):
                            if raw_input.endswith(b'T'):
                                self.ser.write(b'SCIXB START')
                            # self.logger.info('VOOT DETECTED')
                            VOOT = True
                            continue

                    if VOOT and self.game == '5':
                        if raw_input in (b'SCIXB START'):
                            if raw_input.endswith(b'T'):
                                self.ser.write(b'SCIXB START')
                            continue

                        elif raw_input == b'\x01':
                            self.ser.write(b'\x01')
                            
                        elif raw_input == b'\xaa':
                            # RNA side
                            oppside = b'DNA'
                            self.ser.write(b'U')

                        elif raw_input == b'U':
                            # DNA side
                            oppside = b'RNA'
                            self.ser.write(b'\xaa')

                        elif raw_input == b'\x01\x02\x01\x00\x00\x00\x00\x00\x00':
                            self.ser.write(b'\x01\x02\x01\x00\x00\x00\x00\x00\x00')
                            syncing = True
                            VOOT = False
                        continue

                    if syncing:
                        if raw_input == b'U': 
                            # We want to send this to the other tunnel to initiate the connection
                            time.sleep(1) # ensure this arrives after the other side has written the seed.
                            # This part of the handshake doesn't need to be fast.
                            if not self.VOOT_sync:
                                continue
                            else:
                                self.VOOT_sync = None
                                sync = 0
                                syncing = False
                                self.logger.info("starting tunnel DNA Side")
                        elif raw_input == b'\xaa':
                            # We want to send this to the other tunnel to initiate the connection
                            time.sleep(1) # ensure this arrives after the other side has written the seed.
                            # This part of the handshake doesn't need to be fast.
                            if not self.VOOT_sync:
                                continue
                            else:
                                self.VOOT_sync = None
                                sync = 0
                                syncing = False
                                self.logger.info("starting tunnel RNA Side")
                        elif len(raw_input) == 7:
                            # I'm pretty sure this is related to the random number seed. It's the only part of the handshake that is different each attempt.
                            # Random selects break if it's not exchanged correctly and it disconnects after 1 round with an error.
                            # This is also a very timely exchange. If a response is not received very quickly it tries to restart the handshake.
                            # This is likely where internet play breaks down because the handshake has to be fast. However, if we ignore it, the game will go into a handshake re-establishment loop. 
                            # That can buy us time to sync up with the other side, get their seed and write it to the serial port on our time.
                            sync += 1
                            if sync > 150:
                                self.ser.write(raw_input)
                                sync = 0
                                if select.select([],[self.udp],[])[1]:
                                    self.udp.sendto(b'VOOT_RESET', opponent)
                                    self.logger.info('Connection attempt timed out')
                                VOOT = False
                                continue
                            if sync == 1: # if this packet gets dropped, we're in trouble
                                if select.select([],[self.udp],[])[1]:
                                    self.udp.sendto(b'VOOT_SYNC'+ raw_input + b'VOOT_SYNC' + oppside, opponent)
                            if self.VOOT_sync:
                                self.logger.info("Attempting to connect to opponent")
                                self.ser.write(self.VOOT_sync)
                        
                        if syncing:
                            continue
                # if len(raw_input) > 0:
                #     self.logger.info(raw_input)
                payload = raw_input
                seq = str(sequence)
                if len(payload) > 0:
                    
                    packets.insert(0,(payload+self.dataSplit+seq.encode()))
                    if(len(packets) > 5):
                        packets.pop()

                    for i in range(1): #send the data twice. May help with drops or latency    
                        ready = select.select([],[self.udp],[]) #blocking select  
                        if ready[1]:
                            self.udp.sendto(self.packetSplit.join(packets), opponent)
                                
                    sequence+=1
            except Exception as e: 
                self.logger.info(e)
                
                continue
        try:
            time.sleep(2)
            self.close_udp()
            self.logger.info("sender stopped")
        except Exception as e:
            self.logger.info(e)

    def serial_exchange(self, state, opponent):
        self.state = state
        if self.state == "connecting":
            t1 = threading.Thread(target=self.listener,args=(opponent,))
            t2 = threading.Thread(target=self.sender,args=(opponent,))
            if self.ms == "waiting": #we're going to bind to a port. Some users may want to run two instances on one machine, so use different ports for waiting, calling
                Port = 21001
            if self.ms == "calling":
                Port = 21002
            if not self.udp:
                self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.udp.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 184)
                # self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # self.udp.setblocking(0)
                self.udp.bind(('', Port))
                # self.logger.info("UDP bound to: "+str(Port))
            self.udp.settimeout(0.0)

            t1.start()
            t2.start()
            while t1.is_alive:
                t1.join(2)
            while t2.is_alive:
                t2.join(2)

    def register(self, game_id, ip_address, port):
        params = {"action" : 'wait', 
                    "gameID" : game_id, 
                    "client_ip" : ip_address, 
                    "port" : port, 
                    "key" :'mySuperSecretSaturnKey1234'
                }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"}
        url = "https://saturn.dreampipe.net/match_service.php?"
        try:
            r=requests.get(url, params=params, headers=headers)
            r.raise_for_status()
            self.logger.info("Registered for a match")
            return True
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
            self.logger.info("Couldn't connect to matching server")
            self.logger.info(e)
            return False
        
    def get_status(self, game_id, ip_address):
        params = {"action" : 'status', 
                    "gameID" : game_id, 
                    "client_ip" : ip_address, 
                    "key" :'mySuperSecretSaturnKey1234'
                }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"}
        url = "https://saturn.dreampipe.net/match_service.php?"
        try:
            r=requests.get(url, params=params, headers=headers)
            r.raise_for_status()
            status = r.json()["status"]
            if status == "matched":
                dial_string = r.json()["opponent ip_address"]
                address, oppPort = dial_string
                oppPort = int(oppPort)
                opponent = '.'.join(str(int(address[i:i+3])) for i in range(0, len(address), 3))
                return [True, (opponent, oppPort)]
            else:
                return [False, (None, None)]
            
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
            self.logger.info("Couldn't connect to matching server")
            return [False, (None, None)]

    def get_match(self, game_id, ip_address, port):
        params = {"action" : 'match', 
                    "gameID" : game_id, 
                    "client_ip" : ip_address, 
                    "port" : port, 
                    "key" :'mySuperSecretSaturnKey1234'
                }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"}
        url = "https://saturn.dreampipe.net/match_service.php?"
        try:
            r=requests.get(url, params=params, headers=headers)
            r.raise_for_status()
            status = r.json()["status"]
            self.logger.info(status)
            if status == "found opponent":
                dial_string = r.json()["opponent ip_address"]
                address, oppPort = dial_string
                oppPort = int(oppPort)
                opponent = '.'.join(str(int(address[i:i+3])) for i in range(0, len(address), 3))
                return [True, (opponent, oppPort)]
            else:
                return [False, (None, None)]
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
            self.logger.info("Couldn't connect to matching server")
            self.logger.info(e)
            return [False, (None, None)]

    def timed_out(self, game_id, ip_address):
        params = {"action" : 'timeout', 
                    "gameID" : game_id, 
                    "client_ip" : ip_address, 
                    "key" :'mySuperSecretSaturnKey1234'
                }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"}
        url = "https://saturn.dreampipe.net/match_service.php?"
        try:
            r=requests.get(url, params=params, headers=headers)
            r.raise_for_status()
            self.logger.info("Wait timed out. Deregistered from matching server")
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
            self.logger.info("Couldn't connect to matching server")
            return False, None

    def getWanIP(self, Port):
        if not self.udp:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 184)
            # self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp.settimeout(2)
            self.udp.bind(('', Port))

        try:
            nat_type, info  = stun.get_nat_type(s=self.udp, source_ip='', source_port=Port, stun_host="stun.l.google.com", stun_port=19302)
            external_ip = info['ExternalIP']
            external_port = info['ExternalPort']
            external_ip = "".join([x.zfill(3) for x in external_ip.split(".")])
        except AttributeError:
            self.logger.info("Couldn't get WAN information")
            return None, None
        except KeyError:
            return None, None
        return external_ip, external_port
    
    def close_udp(self):
        if self.udp:
            self.udp.close()
            self.udp = None

if __name__ == '__main__':
    link = taisenLink()
    try:
        ms, opponent = link.setup()
        if ms == "waiting":
            state, opponent = link.initConnection()
        else:
            state = "connecting"
        # self.logger.info(state,opponent)
        # do something if state is failed
        if state == "failed":
            try:
                sys.exit(130)
            except SystemExit:
                os._exit(130)
        else:
            link.serial_exchange(state, opponent)
            
    except KeyboardInterrupt:
        link.state = "netlink_disconnected"
        time.sleep(4)
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)