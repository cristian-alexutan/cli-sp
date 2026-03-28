from app.mainwindow import MainWindow
from client.client import Client

sp = Client()
app = MainWindow(sp)

app.run()