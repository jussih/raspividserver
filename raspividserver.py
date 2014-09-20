import sys
import threading
import time
import socket
from datetime import datetime
from optparse import OptionParser
from SocketServer import ThreadingMixIn, TCPServer, BaseRequestHandler


class VideoServer(ThreadingMixIn, TCPServer):
    pass


class VideoStreamHandler(BaseRequestHandler):
    def handle(self):
        thread = threading.current_thread().name
        peer = self.request.getpeername()
        print('[Stream%s] Handling connection from %s'%(thread, peer))

        bytes_count = 0
        filename = str(str(peer[0]) + '_' + datetime.now().strftime('%Y%m%d_%H-%M-%S-%f')) + '.h264'
        f = open(filename, 'wb')
        while True:
            data = self.request.recv(4096)
            if not data:
                break
            f.write(data)
            bytes_count += len(data)
        f.close()
        print('[Stream%s] Connection closed from %s. %d bytes written to file %s'%(thread, peer, bytes_count, filename))


class ControlServer(ThreadingMixIn, TCPServer):
    def __init__(self, data_port, start_event, stop_event, disconnect_event, *args, **kwargs):
        self.data_port = data_port
        self.start_event = start_event
        self.stop_event = stop_event
        self.disconnect_event = disconnect_event
        #self.clients = []
        #self.clients_lock = threading.Lock()
        #return super(ControlServer, self).__init__(*args, **kwargs)
        TCPServer.__init__(self, *args, **kwargs)


class ControlRequestHandler(BaseRequestHandler):
    def handle(self):
        client = self.request.getpeername()[0]
        connection = self.request.makefile('r+b')
        #handshake
        self.p('Sending handshake')
        connection.write('LISTEN %s\n'%self.server.data_port)
        connection.flush()
        reply = connection.readline().strip()
        if reply == 'OK':
            self.p('Client %s connected'%client)
            streaming = False
            ping_timer = 5
            connection_alive = True
            while True:
                try:
                    ping_timer -= 1
                    if ping_timer == 0:
                        connection.write('PING\n')
                        connection.flush()
                        ping_timer = 5
                    if self.server.disconnect_event.is_set():
                        break
                    elif self.server.start_event.is_set() and not streaming:
                        streaming = True
                        self.p('Sending START event')
                        connection.write('START\n')
                        connection.flush()
                        reply = connection.readline().strip()
                        if reply == 'OK':
                            self.p('Client %s is starting streaming'%client)
                    elif self.server.stop_event.is_set() and streaming:
                        streaming = False
                        self.p('Sending STOP event')
                        connection.write('STOP\n')
                        connection.flush()
                        reply = connection.readline().strip()
                        if reply == 'OK':
                            self.p('Client %s is stopping streaming'%client)
                except socket.error:
                    self.p('Client disconnected')
                    connection_alive = False
                    break
                time.sleep(0.5)

            if connection_alive:
                self.p('Closing connection')
                connection.close()
                self.request.close()

        else:
            self.p('Failed connection with %s'%client)

    def p(self, msg):
        print('[Control%s] %s'%(threading.current_thread().name, msg))


def main():
    parser = OptionParser(usage="%prog [options] [args]")
    parser.add_option("--port", default=6666, type=int,
                      help="port number [%default]")

    opts, args = parser.parse_args()

    videoserver = VideoServer(('0.0.0.0', 0), VideoStreamHandler)
    ip, port = videoserver.server_address
    print('Starting videoserver at %s:%d'%(ip, port))
    videoserver_thread = threading.Thread(target=videoserver.serve_forever)
    videoserver_thread.start()

    start_event = threading.Event()
    stop_event = threading.Event()
    disconnect_event = threading.Event()

    controlserver = ControlServer(port, start_event, stop_event, disconnect_event, ('0.0.0.0', opts.port), ControlRequestHandler)
    ip, port = controlserver.server_address
    print('Starting controlserver at %s:%d'%(ip, port))
    try:
        controlserver_thread = threading.Thread(target=controlserver.serve_forever)
        controlserver_thread.start()

        while True:
            sys.stdin.readline()
            if not start_event.is_set():
                print('START')
                start_event.set()
                stop_event.clear()
            else:
                print('STOP')
                start_event.clear()
                stop_event.set()

    except KeyboardInterrupt:
        videoserver.shutdown()
        print('Shut down videoserver')
        stop_event.set()
        disconnect_event.set()
        controlserver.shutdown()
        print('Shut down controlserver')


if __name__ == "__main__":
    main()
