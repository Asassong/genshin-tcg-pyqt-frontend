import socket
from game import Game

server_ip = '127.0.0.1'
server_port = 4095

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((server_ip, server_port))
player_address = []
while True:
    data, addr = s.recvfrom(1024)
    if data == b"connect request":
        if addr not in player_address:
            player_address.append(addr)
            remind_info = {"message": "you have connected to server"}
            s.sendto(str(remind_info).encode(), addr)
    if len(player_address) == 2:
        break

game = Game("Game1", player_address, s)
game.start_game()
