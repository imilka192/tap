from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

if __name__ == '__main__':
    os.chdir(os.path.dirname(__file__))
    server_address = ('localhost', 8000)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    print("✅ Сервер запущен на http://localhost:8000")
    print("📱 WebApp доступен по адресу: http://localhost:8000/webapp.html")
    print("🤖 Telegram бот должен использовать этот URL в тестовом режиме")
    httpd.serve_forever()