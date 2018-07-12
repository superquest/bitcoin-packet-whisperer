"""
Adapted from:
* https://github.com/petertodd/python-bitcoinlib/blob/master/examples/send-addrs-msg.py
* https://github.com/jimmysong/pb-exercises/blob/master/session7/helper.py

Notes:
* It doesn't seem like python-bitcoinlib can really read incoming messages ...
* It's very annoying how python-bitcoinlib's "msg" objects have arbitrarily named data attributes.
Sometimes it's `msg.tx` or `msg.addr` or msg.inv` ...
* How can I tell how many bytes to read beforehand???
"""
import socket, time, bitcoin, hashlib
from io import BytesIO
from bitcoin.messages import msg_version, msg_verack, msg_addr, msg_getdata, MsgSerializable
from bitcoin.net import CAddress, CInv


PORT = 8333
NETWORK_MAGIC = b'\xf9\xbe\xb4\xd9'

bitcoin.SelectParams('mainnet') 


txns = []
addrs = []


def version_pkt(client_ip, server_ip):
    # https://en.bitcoin.it/wiki/Protocol_documentation#version
    msg = msg_version()
    msg.nVersion = 70002
    msg.addrTo.ip = server_ip
    msg.addrTo.port = PORT
    msg.addrFrom.ip = client_ip
    msg.addrFrom.port = PORT

    return msg

def addr_pkt( str_addrs ):
    # https://en.bitcoin.it/wiki/Protocol_documentation#addr
    msg = msg_addr()
    addrs = []
    for i in str_addrs:
        addr = CAddress()
        addr.port = 18333
        addr.nTime = int(time.time())
        addr.ip = i

        addrs.append( addr )
    msg.addrs = addrs
    return msg

def getdata_pkt( inv_vec ):
    # so annoying how this lib doesn't use constructors ...
    msg = msg_getdata()
    msg.inv = inv_vec
    return msg

def connect(server_ip):
    s = socket.socket()

    # The old server_ip value didn't work
    # server_ip = "91.107.64.143"
    # Copied from python-bitcoinlib example
    client_ip = "192.168.0.13"

    s.connect( (server_ip,PORT) )

    # Send Version packet
    s.send( version_pkt(client_ip, server_ip).to_bytes() )
    print('Sent "ver" message')

    # Get Version reply
    # TODO: Should we do something with it? How to read it?
    ver = s.recv(1924)
    print('Received "ver" message')

    # Send Verack
    # https://en.bitcoin.it/wiki/Protocol_documentation#verack
    s.send( msg_verack().to_bytes() )

    # Get Verack
    # TODO: Should we do something with it? How to read it?
    verack = s.recv(1024)
    print('Received "verack" message')

    # Send Addrs
    # FIXME: what address is this?
    # s.send( addr_pkt(["252.11.1.2", "EEEE:7777:8888:AAAA::1"]).to_bytes() )
    # print('Sent "verack" message')
    
    return s


def main_loop(s, f):
    iterations = 0

    while True:
        f()


def int_to_little_endian(n, length):
    '''endian_to_little_endian takes an integer and returns the little-endian
    byte sequence of length'''
    # use the to_bytes method of n
    return n.to_bytes(length, 'little')





def little_endian_to_int(b):
    return int.from_bytes(b, 'little')

def double_sha256(s):
    return hashlib.sha256(hashlib.sha256(s).digest()).digest()


def read_varint(s):
    '''read_varint reads a variable integer from a stream'''
    i = s.read(1)[0]
    if i == 0xfd:
        # 0xfd means the next two bytes are the number
        return little_endian_to_int(s.read(2))
    elif i == 0xfe:
        # 0xfe means the next four bytes are the number
        return little_endian_to_int(s.read(4))
    elif i == 0xff:
        # 0xff means the next eight bytes are the number
        return little_endian_to_int(s.read(8))
    else:
        # anything else is just the integer
        return i


NETWORK_MAGIC = b'\xf9\xbe\xb4\xd9'


class NetworkEnvelope:

    def __init__(self, command, payload):
        self.command = command
        self.payload = payload

    def __repr__(self):
        return '{}: {}'.format(
            self.command.decode('ascii'),
            self.payload.hex(),
        )

    @classmethod
    def parse(cls, s):
        '''Takes a stream and creates a NetworkEnvelope'''
        # FROM HERE https://en.bitcoin.it/wiki/Protocol_documentation#Message_structure
        # check the network magic NETWORK_MAGIC
        magic = s.read(4)
        if magic != NETWORK_MAGIC:
            raise RuntimeError('magic is not right')
        # command 12 bytes
        command = s.read(12)
        # payload length 4 bytes, little endian
        payload_length = little_endian_to_int(s.read(4))
        # checksum 4 bytes, first four of double-sha256 of payload
        checksum = s.read(4)
        # payload is of length payload_length
        payload = s.read(payload_length)
        # verify checksum
        calculated_checksum = double_sha256(payload)[:4]
        if calculated_checksum != checksum:
            raise RuntimeError('checksum does not match')
        return cls(command, payload)

    def serialize(self):
        '''Returns the byte serialization of the entire network message'''
        # add the network magic NETWORK_MAGIC
        result = NETWORK_MAGIC
        # command 12 bytes
        result += self.command
        # payload length 4 bytes, little endian
        result += int_to_little_endian(len(self.payload), 4)
        # checksum 4 bytes, first four of double-sha256 of payload
        result += double_sha256(self.payload)[:4]
        # payload
        result += self.payload
        return result


def read(s):
    magic = s.recv(4)
    if magic != NETWORK_MAGIC:
        raise RuntimeError('Network Magic not at beginning of stream')
    command = s.recv(12)
    payload_length = little_endian_to_int(s.recv(4))
    checksum = s.recv(4)
    payload = s.recv(payload_length)
    # check the checksum
    if double_sha256(payload)[:4] != checksum:
        raise RuntimeError('Payload and Checksum do not match')
    return command, payload

def _read(s):
    magic = s.recv(4)
    if magic != NETWORK_MAGIC:
        raise RuntimeError('Network Magic not at beginning of stream')
    command = s.recv(12)
    payload_length = little_endian_to_int(s.recv(4))
    checksum = s.recv(4)
    payload = s.recv(payload_length)
    # check the checksum
    if double_sha256(payload)[:4] != checksum:
        raise RuntimeError('Payload and Checksum do not match')
    return command, payload


def handle_commands_loop(s):
    while True:
        data = s.recv(1024* 100)

        try:
            # FIXME: this is broken. Can I just stream from the socket???
            msg = MsgSerializable.from_bytes(data)
        except Exception as e:
            print(f'Message deserialization failed: {e}')
            continue

        if msg.command == b'inv':
            # https://en.bitcoin.it/wiki/Protocol_documentation#getdata
            # msg.inv is actually an inv_vec
            m = getdata_pkt(msg.inv)
            s.send(m.to_bytes())
            print(f'Sent "inv" message: {msg.inv}')

        if msg.command == b'tx':
            txns.append(msg.tx)
            print(f'Received "tx": {msg.tx}')

        if msg.command == b'addr':
            addrs.extend(msg.addrs)
            print(f'Received "addrs": {msg.addrs}')

        # HACK
        iterations += 1
        if iterations % 10 == 0:
            print(f"#txns: {len(txns)}")
            print(f"#addrs: {len(addrs)}")


def log(s):
    while True:
        data = s.recv(1024)

        try:
            # FIXME: this is broken. Can I just stream from the socket???
            msg = MsgSerializable.from_bytes(data)
        except Exception as e:
            print(f'Message deserialization failed: {e}')
            continue

        print(msg)


def _log(s):
    while True:
        try:
            command, payload = read(s)
            print(command, payload)
        except RuntimeError as e:
            print('error reading from socket')



def read_and_log(s):
    while True:
        try:
            command, payload = read(s)
            print(command, payload)
        except RuntimeError as e:
            print('error reading from socket')

        continue

        if command.startswith(b'inv'):

            print('!!!')

            stream = BytesIO(payload)
            count = read_varint(stream)

            for _ in range(count):
                command = stream.read(4)
                payload = stream.read(32)
                e = NetworkEnvelope(command, payload)

                msg = e.serialize()
                print(f'Sending {e}')
                try:
                    s.send(msg)
                except Exception as e:
                    print(e)



def main():
    ip = '39.104.83.148'
    ip = '190.210.234.38'

    s = connect(ip)
    _log(s)


if __name__ == '__main__':
    main()