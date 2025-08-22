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
try:
    import stun
except ImportError:
    os.system('pip install pystun3')
    import stun

osName = os.name
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Tunnel')
logger.setLevel(logging.INFO)
pinging = True
printout = False
packetSplit = b"<packetSplit>"
dataSplit = b"<dataSplit>"
com_port = None
game = None
baud = None
ms = None
dial_string = None
ping = time.time()
matching = None
VOOT_sync = None
ping_rate = 2

if sys.version_info < (3,0,0):
    input = raw_input

def setup(com_port = com_port, game = game, ms = ms, dial_string = dial_string, matching=matching, baud=baud):
    opponent = None
    for arg in sys.argv[1:]:
        if len(arg.split("=")[1].strip()) == 0:
            continue
        elif arg.split("=")[0] == "com":
            com_port = arg.split("=")[1].strip()
        elif arg.split("=")[0] == "game":
            game = arg.split("=")[1].strip()
        elif arg.split("=")[0] == "state":
            ms = arg.split("=")[1].strip()
        elif arg.split("=")[0] == "address":
            dial_string = arg.split("=")[1].strip()
        elif arg.split("=")[0] == "baud":
            baud = int(arg.split("=")[1].strip())
        elif arg.split("=")[0] == "matching":
            matching = arg.split("=")[1].strip()
    
    if dial_string and ms:
        if ms == 'calling':
            opponent = (dial_string, 21001)                     
    
    while True:
        if not com_port:
            com_port = input("\nCOM port: ")
            if "COM" in com_port.upper():
                com_port = com_port.upper()
            if com_port.startswith("tty"):
                com_port = "/dev/" + com_port
            try:
                int(com_port)
                com_port = "COM" + com_port
            except ValueError:
                pass
        try:
            print("Trying " + str(com_port))
            testCon = serial.Serial(com_port,9600)
            testCon.close()
            break
        except serial.SerialException:
            print("Invalid COM port")
            com_port = None
            continue
    print("\nUsing %s" % com_port)

    while True:
        
        if game == '1':
            baud = 28800
        elif game == '2':
            baud = 38400
        elif game == '3':
            baud = 230400
        elif game == '4':
            baud = 14400
        elif game == '5':
            baud = 260416
        elif game == '6':
            baud = 57600
        elif game == '7':
            try:
                baud = int(input("\ncustom baud: "))
                int(baud)
            except ValueError:
                print("Invalid selection")
                game = None
                baud = None
                continue
        elif game == '8':
            try:
                multiplier = int(input("\nSCBRR2 multiplier: "))
                int(multiplier)
                baud = int(round((50*1000000)/(multiplier+1)/32,0))
                print(baud)
            except ValueError:
                print("Invalid selection")
                game = None
                baud = None
                continue
        else:
            # print("invalid selection")
            game = None
            
        if game:
            break
        game = input("\nGame:\r\n[1] Aero Dancing F\r\n[2] Aero Dancing I\r\n[3] F355\r\n[4] Sega Tetris\r\n[5] Virtual On\r\n[6] Hell Gate\r\n[7] custom\r\n[8] calculated\r\n"
            )
        continue



    if not dial_string:
        while True:
            if matching == "2":
                dial_string = input("Opponent IP address: ")
            elif matching == "1":
                dial_string = "3" + str(game)
                my_ip, ext_port = getWanIP(21002)
                if my_ip:
                    status, opponent = get_match(dial_string[-2:], my_ip, ext_port)
                    if status:
                        # logger.info(opponent)
                        ms = "calling"
                    else:
                        ms = "waiting"
                else:
                    ms = None
                    print("Error getting WAN info.")
            else:
                matching = None
            if matching:
                break
            matching = input("[1] Use matchmaking server\r\n[2] Enter IP Address\r\n")
            
    while True:
        if ms:
            break
        side = input('\nWait or connect:\n[1] Wait\n[2] Connect\n')
        if side == '1' or side =='2':
            if side == '1':
                ms = "waiting"
            else:
                ms = "calling"
                opponent = (dial_string, 21001)
        else:
            print('Invalid selection')
            ms = None
            continue

    print("setting serial rate to: %s" % baud)
    ser = serial.Serial(com_port, baudrate=baud, rtscts=True)
    ser.reset_output_buffer() #flush the serial output buffer. It should be empty, but doesn't hurt.
    ser.reset_input_buffer()
    ser.timeout = None
    variables = (
        ms,
        dial_string,
        ser,
        opponent
    )
    return variables

def initConnection(ms,dial_string):
    if len(dial_string) > 2:
        opponent = dial_string.replace('*','.')
        ip_set = opponent.split('.')
        for i,set in enumerate(ip_set): #socket connect doesn't like leading zeroes now
            fixed = str(int(set))
            ip_set[i] = fixed
        if ms == "waiting":
            oppPort = 21002
        else:
            oppPort = 21001
        opponent = (('.').join(ip_set), oppPort)
        return ("connecting",opponent)

    elif len(dial_string) == 2:
        if ms == "waiting":
            registered = False
            timerStart = time.time()
            while True:
                if time.time() - timerStart > 240:
                    return ["failed", None]
                my_ip, ext_port = getWanIP(21001)
                if my_ip:
                    if not registered:
                        if register(dial_string[-2:], my_ip, ext_port):
                            registered = True
                    elif registered:
                        status, opponent = get_status(dial_string[-2:], my_ip)
                        if status:
                            logger.info("found opponent")
                            # logger.info(opponent)
                            return ["connecting",opponent]
                else:
                    logger.info("Couldn't get WAN information. Won't register for match. Trying again in 3 seconds")
                time.sleep(ping_rate)


        
    return ["failed", None]


    



def serial_exchange(side, state, opponent, ser):
    
    def listener(ser=ser):
        global ping
        global state
        global VOOT_sync
        first_run = True
        lastPing = 0
        pong = time.time()
        startup = time.time()
        jitterStore = []
        pingStore = []
        currentSequence = 0
        maxPing = 0
        maxJitter = 0
        recoveredCount = 0
        while(state != "netlink_disconnected"):
            ready = select.select([udp],[],[],0) #polling select
            if ready[0]:
                try:
                    packetSet = udp.recv(1024)
                    while time.time() - startup < 3:
                        # Discard packets for 3 seconds in case there are any in the OS buffer.
                        continue
                    #start pinging code block
                    # if pinging == True:
                    if packetSet == b'PING_SHIRO':
                        udp.sendto(b'PONG_SHIRO', opponent)
                        continue
                    elif packetSet == b'RESET_COUNT_SHIRO':
                        # If peer reset their tunnel, we need to reset our sequence counter.
                        print("Packet sequence reset")
                        currentSequence = 0
                        continue
                    elif b'VOOT_SYNC' in packetSet:
                        print("\r\nVOOT connection attempt. Choose " + packetSet.split(b'VOOT_SYNC')[2].decode() )
                        VOOT_sync = packetSet.split(b'VOOT_SYNC')[1]
                        continue
                    elif packetSet == b'VOOT_RESET':
                        print("VOOT synced")
                        VOOT_sync = None
                        continue
                    elif packetSet == b'PONG_SHIRO':
                        if first_run:
                            print("Connection established. Begin link play\r\n")
                            udp.sendto(b'RESET_COUNT_SHIRO', opponent) 
                            # we know there's a peer because it responded to our ping
                            # tell it to reset its sequence counter
                            first_run = False
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
                        if osName != 'posix' and pinging == True:
                            sys.stdout.write('Ping: %s Max: %s | Jitter: %s Max: %s | Avg Ping: %s |  Avg Jitter: %s | Recovered Packets: %s         \r' % (pingResult,maxPing,jitter, maxJitter,pingAvg,jitterAvg,recoveredCount))
                        lastPing = pingResult
                        continue
                    #end pinging code block

                    packets= packetSet.split(packetSplit)
                    try:
                        while True:
                            packetNum = 0
                            
                            #go through all packets 
                            for p in packets:
                                if int(p.split(dataSplit)[1]) == currentSequence:
                                    break
                                packetNum += 1
                                
                            #if the packet needed is not here,  grab the latest in the set
                            if packetNum == len(packets):
                                packetNum = 0
                            if packetNum > 0 :
                                recoveredCount += 1
                            message = packets[packetNum]
                            payload = message.split(dataSplit)[0]
                            sequence = message.split(dataSplit)[1]
                            if int(sequence) < currentSequence:
                                break  #All packets are old data, so drop it entirely
                            currentSequence = int(sequence) + 1
                            toSend = payload
                            # logger.info(binascii.hexlify(payload))
                            if printout:
                                logger.info(b'net received: '+ toSend)
                            # logger.info(b'net received: '+ toSend)
                            ser.write(toSend)
                            if packetNum == 0: # if the first packet was the processed packet,  no need to go through the rest
                                break

                    except IndexError:
                        continue
                except ConnectionResetError:
                    continue
                    
        logger.info("listener stopped")        
                
    def sender(side,opponent, ser=ser):
        global ping
        global state
        global VOOT_sync
        global printout
        sequence = 0
        packets = []
        first_run = True
        VOOT = False
        mirror = False
        sync = 0
        oppside = b''
        
        while(state != "netlink_disconnected"):
            if time.time() - ping >= ping_rate:
                try:
                    udp.sendto(b'PING_SHIRO', opponent)
                except ConnectionResetError:
                    pass
                ping = time.time()
            raw_input = b''
            if ser.in_waiting > 0:
                # print(ser.in_waiting)
                raw_input += ser.read(ser.in_waiting)
            if len(raw_input) > 0 and printout:
                logger.info(b'serial read: '+ raw_input)
            
            try:
                if len(raw_input) > 0:
                    # VOOT has a very finicky handshake and spoofing most of it makes things much easier.
                    if not VOOT:
                        
                        if raw_input == b'SCIXB STA':
                            # logger.info('VOOT DETECTED')
                            VOOT = True
                            continue
                        elif raw_input == b'SCIXB START':
                            # logger.info('VOOT DETECTED')
                            ser.write(b'SCIXB START')
                            VOOT = True
                            continue

                    if VOOT:
                        if raw_input == b'RT':
                            ser.write(b'SCIXB START')

                        elif raw_input == b'SCIXB START':
                            ser.write(b'SCIXB START')

                        elif raw_input == b'\x01':
                            ser.write(b'\x01')
                            
                        elif raw_input == b'\xaa':
                            # RNA side
                            oppside = b'DNA'
                            ser.write(b'U')

                        elif raw_input == b'U':
                            # DNA side
                            oppside = b'RNA'
                            ser.write(b'\xaa')

                        elif raw_input == b'SCIXB STA':
                            pass

                        elif raw_input == b'\x01\x02\x01\x00\x00\x00\x00\x00\x00':
                            ser.write(b'\x01\x02\x01\x00\x00\x00\x00\x00\x00')
                            mirror = True
                            VOOT = False
                        continue

                    if mirror:
                        if raw_input == b'U': 
                            # We want to send this to the other tunnel to initiate the connection
                            time.sleep(1) # ensure this arrives after the other side has written the seed.
                            # This part of the handshake doesn't need to be fast.
                            if not VOOT_sync:
                                continue
                            else:
                                VOOT_sync = None
                                sync = 0
                                mirror = False
                                logger.info("starting tunnel DNA Side")
                        elif raw_input == b'\xaa':
                            # We want to send this to the other tunnel to initiate the connection
                            time.sleep(1) # ensure this arrives after the other side has written the seed.
                            # This part of the handshake doesn't need to be fast.
                            if not VOOT_sync:
                                continue
                            else:
                                VOOT_sync = None
                                sync = 0
                                mirror = False
                                logger.info("starting tunnel RNA Side")
                        elif len(raw_input) == 7:
                            # I'm pretty sure this is related to the random number seed. It's the only part of the handshake that is different each attempt.
                            # Random selects break if it's not exchanged correctly and it disconnects after 1 round with an error.
                            # This is also a very timely exchange. If a response is not received very quickly it tries to restart the handshake.
                            # This is likely where internet play breaks down because the handshake has to be fast. However, if we ignore it, the game will go into a handshake re-establishment loop. 
                            # That can buy us time to sync up with the other side, get their seed and write it to the serial port on our time.
                            sync += 1
                            if sync > 150:
                                ser.write(raw_input)
                                sync = 0
                                udp.sendto(b'VOOT_RESET', opponent)
                                logger.info('Connection attempt timed out')
                                VOOT = False
                                continue
                            if sync == 1: # if this packet gets dropped, we're in trouble
                                udp.sendto(b'VOOT_SYNC'+ raw_input + b'VOOT_SYNC' + oppside, opponent)
                            if VOOT_sync:
                                logger.info("Wrote random seed")
                                ser.write(VOOT_sync)
                        # else:
                        #     # this is just here to mirror inputs for testing. delete for real play.
                        #     ser.write(raw_input)
                        # mirror = False
                        if mirror:
                            continue
                # if len(raw_input) > 0:
                #     print(raw_input)
                payload = raw_input
                seq = str(sequence)
                if len(payload) > 0:
                    
                    packets.insert(0,(payload+dataSplit+seq.encode()))
                    if(len(packets) > 5):
                        packets.pop()
                        
                    for i in range(1): #send the data twice. May help with drops or latency    
                        ready = select.select([],[udp],[]) #blocking select  
                        if ready[1]:
                            udp.sendto(packetSplit.join(packets), opponent)
                                
                    sequence+=1
            except Exception as e: 
                print(e)
                
                continue
        try:
            udp.close()
            logger.info("sender stopped")
        except Exception as e:
            print(e)
             
    if state == "connecting":
        t1 = threading.Thread(target=listener)
        t2 = threading.Thread(target=sender,args=(side,opponent))
        if side == "waiting": #we're going to bind to a port. Some users may want to run two instances on one machine, so use different ports for waiting, calling
            Port = 21001
        if side == "calling":
            Port = 21002
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 184)
        udp.setblocking(0)
        udp.bind(('', Port))

        t1.start()
        t2.start()
        while t1.is_alive:
            t1.join(2)
        while t2.is_alive:
            t2.join(2)

def register(game_id, ip_address, port):
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
        logger.info("Registered for a match")
        return True
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
        logger.info("Couldn't connect to matching server")
        logger.info(e)
        return False
    
def get_status(game_id, ip_address):
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
        logger.info("Couldn't connect to matching server")
        return [False, (None, None)]

def get_match(game_id, ip_address, port):
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
        logger.info(status)
        if status == "found opponent":
            dial_string = r.json()["opponent ip_address"]
            address, oppPort = dial_string
            oppPort = int(oppPort)
            opponent = '.'.join(str(int(address[i:i+3])) for i in range(0, len(address), 3))
            return [True, (opponent, oppPort)]
        else:
            return [False, (None, None)]
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
        logger.info("Couldn't connect to matching server")
        logger.info(e)
        return [False, (None, None)]

def timed_out(game_id, ip_address):
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
        logger.info("Wait timed out. Deregistered from matching server")
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
        logger.info("Couldn't connect to matching server")
        return False, None

def getWanIP(port):
    try:
        nat_type, external_ip, external_port = stun.get_ip_info(source_port=port, stun_host="stun2.l.google.com", stun_port=19302)
        external_ip = "".join([x.zfill(3) for x in external_ip.split(".")])
    except AttributeError:
        logger.info("Couldn't get WAN information")
        return None, None
    return external_ip, external_port

if __name__ == '__main__':
    try:
        ms, dial_string, ser, opponent = setup()
        if ms == "waiting":
            state, opponent = initConnection(ms,dial_string)
        else:
            state = "connecting"
        # print(state,opponent)
        serial_exchange(ms, state, opponent, ser)
    except KeyboardInterrupt:
        state = "netlink_disconnected"
        print('Interrupted')
        time.sleep(4)
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)