import sys
import threading
import socket
import time
import picamera
from optparse import OptionParser


def create_socket(address, port):
    client_socket = socket.socket()
    client_socket.connect((address, port))
    return client_socket


class VideoStream(threading.Thread):
    def __init__(self, address, port, stop_event, is_streaming, *args, **kwargs):
        self.address = address
        self.port = port
        self.stop_event = stop_event
        self.is_streaming = is_streaming
        self.camera = picamera.PiCamera()
        self.camera.resolution = (640, 480)
        self.camera.framerate = 24
        super(VideoStream, self).__init__(*args, **kwargs)

    def run(self):
        print('[%s] Stream starting'%threading.current_thread().name)
        self.start_stream()
        self.stop_event.wait()
        print('[%s] Stream stopping'%threading.current_thread().name)
        self.stop_stream()

    def start_stream(self):
        self.is_streaming.set()
        self.socket = create_socket(self.address, self.port)
        # Make a file-like object out of the connection
        self.connection = self.socket.makefile('wb')
        # Start a preview and let the camera warm up for 2 seconds
        self.camera.start_preview()
        time.sleep(2)
        self.camera.start_recording(self.connection, format='h264')

    def stop_stream(self):
        self.camera.stop_recording()
        self.camera.close()
        self.connection.close()
        self.socket.close()
        self.stop_event.clear()
        self.is_streaming.clear()


def main():
    parser = OptionParser(usage="%prog [options] [args]")
    parser.add_option("--server", type=str,
                      help="server address")
    parser.add_option("--port", default=6666, type=int,
                      help="port number [%default]")

    opts, args = parser.parse_args()
    server = opts.server
    port = opts.port

    stop_event = threading.Event()
    is_streaming = threading.Event()
    net_socket = create_socket(server, port)
    connection = net_socket.makefile('r+b')
    #handshake
    print('Waiting for handshake')
    command = connection.readline().split()
    print('Handshake command: %s'%command)
    if len(command) == 2 and command[0] == 'LISTEN':
        data_port = int(command[1])
    else:
        print('Handshake failed!')
        sys.exit(1)
    connection.write('OK\n')
    connection.flush()
    print('Handshake success, waiting for commands')
    try:
        while True:
            command = connection.readline()
            if command != 'PING\n':
                print('Received command: %s'%command)
            if not command:
                break
            if command == 'START\n':
                if is_streaming.is_set():
                    connection.write('NOK\n')
                    connection.flush()
                else:
                    print('Starting stream')
                    stream = VideoStream(server, data_port, stop_event, is_streaming)
                    stream.start()
                    connection.write('OK\n')
                    connection.flush()
            elif command == 'STOP\n':
                print('Stopping stream')
                stop_event.set()
                connection.write('OK\n')
                connection.flush()
            else:
                connection.write('NOK\n')
                connection.flush()
        stop_event.set()
    except KeyboardInterrupt:
        stop_event.set()
        connection.close()
        net_socket.shutdown(socket.SHUT_RDWR)
        net_socket.close()
        print('Stopping...')
        print('Bye!')


if __name__ == "__main__":
    main()
