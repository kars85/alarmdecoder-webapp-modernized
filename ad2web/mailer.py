import smtplib
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate


class Mailer:
    port = 25
    server = "127.0.0.1"
    tls = False
    authentication_required = False
    username = None
    password = None

    def __init__(
        self,
        server="127.0.0.1",
        port=25,
        tls=False,
        authentication_required=False,
        username=None,
        password=None,
    ):
        self.port = port
        self.server = server
        self.tls = tls
        self.authentication_required = authentication_required
        self.username = username
        self.password = password

    def update_username(self, username):
        self.username = username

    def update_password(self, password):
        self.password = password

    def update_server(self, server):
        self.server = server

    def update_port(self, port):
        self.port = int(port)

    def update_tls(self, tls):
        self.tls = tls

    def update_auth(self, auth):
        self.authentication_required = auth  # Fixed reference

    def send_mail(self, send_from, send_to, subject, text, files=None):
        assert isinstance(send_to, list)
        if files is not None:
            assert isinstance(files, list)

        msg = MIMEMultipart()
        msg["From"] = send_from
        msg["To"] = ", ".join(send_to)
        msg["Date"] = formatdate(localtime=True)
        msg["Subject"] = subject
        msg.attach(MIMEText(text))

        for f in files or []:
            with open(f, "rb") as fil:
                part = MIMEApplication(fil.read(), Name=basename(f))
                part["Content-Disposition"] = f'attachment; filename="{basename(f)}"'
                msg.attach(part)

        smtp = smtplib.SMTP(self.server, self.port)

        if self.tls:
            smtp.starttls()

        if self.authentication_required:
            smtp.login(str(self.username), str(self.password))

        smtp.sendmail(send_from, send_to, msg.as_string())
        smtp.close()
