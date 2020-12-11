import sys
import time
import socket
import threading
import struct

# definitions of variables
PORT_BASE = 12000 #each peer listens to 12000 + i
LOCALIP = "127.0.0.1"
PINGTIMEOUT = 1.0
UDPBUFFER = 1024 # maximum bytes ping buffer can be
TCPBUFFER = 1024 # maximum byes TCP channel can be
ACK_ACCUMULATION_MAX = 3 #max amount of ACKS before assumes peer is dead

#dictionary to determine message types
# messages can be called either way to help make code readable.
MESSAGETYPE = {0:'pingreq', 1:'pingres', 2:'lostpeer', 3:'quit', 4:'filereq', 5:'fileres', 6:'joinreq', 7:'joinres', 8:'changesucc'}
ENCR_MTYPE = {'pingreq':0, 'pingres':1, 'lostpeer':2, 'quit':3, 'filereq':4, 'fileres':5, 'joinreq': 6, 'joinres': 7, 'changesucc': 8}


class Peer:
    def __init__(self,id,pred,succ1,succ2, ping):
        self.id = id
        self.port = PORT_BASE + id
        self.pred = None
        self.succ1 = succ1
        self.succ2 = succ2
        self.ping = ping

        if self.succ2 is None:
            tNew = threading.Thread(target= self.join_request)
            tNew.daemon = True
            tNew.start()

        if self.succ2 != None:
            #function pinging successor 1
            t1 = threading.Thread(target = self.send_ping, args = (1,))
            t1.daemon = True
            t1.start()

            #function pinging sucsessor 2
            t2 = threading.Thread(target = self.send_ping, args = (2,))
            t2.daemon = True
            t2.start()

        #function listening for input
        t0 = threading.Thread(target=self.listen_input)
        t0.start()


        #function listening to UDP
        t3 = threading.Thread(target=self.listen_UDP)
        t3.daemon = True
        t3.start()

        #function listening to TCP
        t4 = threading.Thread(target=self.listen_TCP)
        t4.daemon = True
        t4.start()

    

    # creates byte array message to incorporate sender ID and extra information when needed
    def message_helper(self, mtype, info1 = None, info2 = None, info3 = None):
        message = bytearray([mtype])
        message.extend( struct.pack("B", self.id))
        if info1 != None:
            message.extend( struct.pack("B", info1))
        if info2 != None:
            message.extend( struct.pack("B", info2))
        if info3 != None:
            message.extend( struct.pack("B", info3))    
        return message

    # evaluates the amount of sequences that have been missed
    def sequence_evaluator(self,last_sequence,next_sequence):
        if next_sequence >= last_sequence:
            return next_sequence - last_sequence
        else:
            return 255 - last_sequence + next_sequence + 1

    # If no ping ACK and a peer is dead, this function updates peers through TCP
    # divided into the two cases for succ1 and succ2
    # succ1 updates immediately moving second forward then pinging that successor
    # succ2 waits for ping freq for the next sucessor to update then contacts for information
    def lost_peer(self, succ_number):
        TCP_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        message = self.message_helper(ENCR_MTYPE['lostpeer'])
        lostPeer = None
        if succ_number == 1: #assume first sucessor is lost
            lostPeer = self.succ1
            self.succ1 = self.succ2
            TCP_socket.connect((LOCALIP,PORT_BASE+self.succ2))
        elif succ_number == 2:
            time.sleep(self.ping+1) # sleep long enough to allow sucessors sucessor to update
            TCP_socket.connect((LOCALIP,PORT_BASE+self.succ1))
        TCP_socket.send(message)
        data = TCP_socket.recvfrom(TCPBUFFER)
        self.succ2 = int(data[0])
        TCP_socket.close()
        if self.succ1 != self.id: #case for two nodes and one quits
            print(f'Peer {lostPeer} is no longer alive')
            print(f'My first successor is now peer {self.succ1}')
            print(f'My second sucessor is now peer {self.succ2}')
        else:
            print("I'm last peer on network, I have no successors")
            self.succ1 = None
            self.succ2 = None


    # function to send_pings via UDP to successors
    def send_ping(self,indicator):
        last_sequence = 0
        sequenceNum = 0
        while True:
            if indicator == 1:
                targetID = self.succ1
            else:
                targetID = self.succ2
            if not targetID or targetID == self.id:
                return
            UDP_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            message = self.message_helper(ENCR_MTYPE['pingreq'],indicator,sequenceNum)
            # sets timeout if package isn't received in time (1 second in this case)
            UDP_socket.settimeout(PINGTIMEOUT)
            UDP_socket.sendto(message,(LOCALIP,PORT_BASE+targetID))
            try:
                data,addr = UDP_socket.recvfrom(UDPBUFFER)
                responseID = int(data[1])
                if MESSAGETYPE[data[0]] == 'pingres':
                    print(f"Ping response received from Peer {responseID}")
                    last_sequence = sequenceNum
            except socket.timeout:
                ACK_accumulation = self.sequence_evaluator(last_sequence,sequenceNum)
                if ACK_accumulation:
                    print(f"No ping response from Peer {targetID}")
                if ACK_accumulation > ACK_ACCUMULATION_MAX: #succ is dead
                    print(f'Peer {targetID} is no longer alive.')
                    self.lost_peer(indicator)
            sequenceNum = (sequenceNum+1)%256 # next sequence number 
            time.sleep(self.ping)
        UDP_socket.close()
    

    #function to listen to UDP message and return messages
    def listen_UDP(self):
        Server_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        Server_socket.bind((LOCALIP,self.port))
        while True:
            data, addr = Server_socket.recvfrom(UDPBUFFER)
            if data is None: break
            senderID = int(data[1])
            if MESSAGETYPE[data[0]] == 'pingreq':
                ## if Ping is from first sucessor, update the predecessor qui
                if data[2] == 1:
                    self.pred = int(senderID)
                print(f"A ping request message was received from Peer {senderID}")
                message = self.message_helper(ENCR_MTYPE['pingres'],data[3])
                Server_socket.sendto(message,addr)

        Server_socket.close()


    #function for listening to TCP messages
    def listen_TCP(self):
        Server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        Server_socket.bind((LOCALIP,self.port))
        Server_socket.listen()
        while True:
            Connection_socket, addr = Server_socket.accept()
            data = Connection_socket.recv(TCPBUFFER)
    
            try:

                if MESSAGETYPE[data[0]] == 'quit': # quit message received (update sucessors)                             
                    quitPeer = self.succ1
                    if int(data[1]) == self.succ1:
                        TCP_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        if int(data[2]) == self.id:
                            print(f'Peer {quitPeer} will depart from the network')
                            print("I'm last peer on network, I have no successors")
                            self.succ1 = None
                            self.succ2 = None
                        else: 
                            self.succ1 = int(data[2])
                            self.succ2 = int(data[3])
                        TCP_socket.connect((LOCALIP,PORT_BASE+self.pred))
                        TCP_socket.send(data)
                        TCP_socket.close()
                    elif int(data[1]) == self.succ2:
                        quitPeer = self.succ2
                        self.succ2 = int(data[2])
                    if self.succ1 and self.succ2:
                        print(f'Peer {quitPeer} will depart from the network')
                        print(f'My new first successor is peer {self.succ1}')
                        print(f'My new second sucessor is peer {self.succ2}')

                elif MESSAGETYPE[data[0]] == 'lostpeer': #lost peer message received
                    # return a message containing my successor
                    message = str(self.succ1).encode('utf-8')
                    Connection_socket.send(message)

                elif MESSAGETYPE[data[0]] == 'joinreq' : #join request from peer
                    TCP_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    if self.succ1 > data[1] :
                        print(f'Peer {data[1]} Join request forwarded to my sucessor')
                        TCP_socket.connect((LOCALIP,PORT_BASE+self.succ1))
                        message = self.message_helper(ENCR_MTYPE['joinreq'],data[1])
                        
                        TCP_socket.send(message)
                    elif self.pred < data[1]: 
                        print(f'Peer {data[1]} Join request received ')
                        TCP_socket.connect((LOCALIP,PORT_BASE+data[1]))
                        message = self.message_helper(ENCR_MTYPE['joinres'],data[1])
                        TCP_socket.send(message)
                    else :
                        print(f'Peer {data[1]} Join request forwarded to mys successor')
                        TCP_socket.connect((LOCALIP,PORT_BASE+self.succ1))
                        message = self.message_helper(ENCR_MTYP['joinreq'],data[1])
                    TCP_socket.close()

                elif MESSAGETYPE[data[0]] == 'joinres': #join response from peer
                    print(f'HIIIII Join request has been accepted')
                data = None
                
            except ConnectionRefusedError:
                print("Couldn't connect to peer, please wait to try again")
            
            Connection_socket.close()



    #if quit is called, it informs the peers of departure
    def quit_function(self):
        if self.pred == None:
            time.sleep(self.ping+1) #waits 5 seconds to check if predecessors just havent been updated.
        try:
            print(f'Peer {self.id} will depart from the network')
            print("please allow a few seconds before subsuquent quit functions to allow peers to update")
            message = self.message_helper(ENCR_MTYPE['quit'],self.succ1,self.succ2)
            TCP_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            TCP_socket.connect((LOCALIP,PORT_BASE+self.pred))
            TCP_socket.send(message)
            TCP_socket.close()
            sys.exit(0)
        except (TypeError,ConnectionRefusedError): #case where it's the only node left
            sys.exit(0) 

    # function to constantly listen to input
    def listen_input(self):
        while (True):
            if inp == 'Quit':
                self.quit_function()
            else:
                print("Incorrect input: input doesn't match any function")
 
    def join_request(self):
        print("inside function")
        try:
            message = self.message_helper(ENCR_MTYPE['joinreq'],self.id)
            TCP_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f'COONNECTING TOOOOOOO {self.succ1}')
            TCP_socket.connect((LOCALIP,PORT_BASE+self.succ1))
            TCP_socket.send(message)
            TCP_socket.close()
            sys.exit(0)
        except (TypeError,ConnectionRefusedError): #case where it's the only node left
            sys.exit(0) 
    

if __name__ == "__main__":

    for i in range(2,len(sys.argv)):
        sys.argv[i]=int(sys.argv[i])

    if str(sys.argv[1]) == 'init': 
        print ("Ping requests were sent to Peers " + str(sys.argv[3]) + " and " + str(sys.argv[4]))

        peer = Peer(sys.argv[2],None,sys.argv[3],sys.argv[4], sys.argv[5])
    elif str(sys.argv[1]) == 'join':
        peer = Peer(sys.argv[2],None,sys.argv[3],None, sys.argv[4])
