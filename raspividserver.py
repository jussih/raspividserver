import threading
from datetime import datetime
from optparse import OptionParser
from SocketServer import ThreadingMixIn, TCPServer, BaseRequestHandler


class VideoServer(ThreadingMixIn, TCPServer):
    pass


class VideoStreamHandler(BaseRequestHandler):
    def handle(self):
        thread = threading.current_thread().name
        peer = self.request.getpeername()
        print('[%s] Handling connection from %s'%(thread, peer))

        bytes_count = 0
        filename = str(datetime.now().strftime('%Y%m%d_%H-%M-%S-%f')) + '.h264'
        f = open(filename, 'wb')
        while True:
            data = self.request.recv(4096)
            if not data:
                break
            f.write(data)
            bytes_count += len(data)
        f.close()
        print('[%s] Connection closed from %s. %d bytes written to file %s.'%(thread, peer, bytes_count, filename))


def main():
    parser = OptionParser(usage="%prog [options] [args]")
    parser.add_option("--port", default=6666, type=int,
                      help="port number [%default]")

    opts, args = parser.parse_args()

    server = VideoServer(('', opts.port), VideoStreamHandler)
    ip, port = server.server_address
    print('Starting server at %s:%d'%(ip, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print('Shutting down')


if __name__ == "__main__":
    main()
