import threading
import time
from queue import Queue
import smtplib, ssl
import csv
from datetime import datetime


class Outbox:
    _queue = Queue()
    __flush_interval = None
    __flush_thread = None
    __max__queue_size = 1
    __sender_credentials = {"email": None, "password": None}
    __stop_flush_thread = False  # flag
    __smtp_error_occurred = False
    __working = False

    @staticmethod
    def _set_flush_interval(val):
        if not isinstance(val, int):
            raise TypeError(
                "start() method argument 'flush_interval' must be of type 'int'"
            )
        if val < 0:
            raise ValueError(
                "start() method argument 'flush_interval' must be a positive integer"
            )
        Outbox.__flush_interval = val

    @staticmethod
    def _set_max_size(val):
        if not isinstance(val, int):
            raise TypeError(
                "start() method argument 'max__queue_size' must be of type 'int'"
            )
        if val < 1:
            raise ValueError(
                "start() method argument 'max__queue_size' must be an integer greater than 0"
            )
        Outbox.__max__queue_size = val

    @staticmethod
    def _set_credentials(credentials):
        if (
            not isinstance(credentials, dict)
            or "email" not in credentials
            or "password" not in credentials
        ):
            raise TypeError(
                "start() method argument 'sender_credentials' must be of type 'dict' with keys 'email' and 'password'"
            )
        if not isinstance(credentials["email"], str) or not isinstance(
            credentials["password"], str
        ):
            raise ValueError(
                "dict 'sender_credentials' keys, 'email' and 'password' must be of type 'str'"
            )
        Outbox.__sender_credentials["email"] = credentials["email"]
        Outbox.__sender_credentials["password"] = credentials["password"]

    @staticmethod
    def smtp_error_occurred():
        return Outbox.__smtp_error_occurred

    @staticmethod
    def is_working():
        return Outbox.__working

    @staticmethod
    def start(flush_interval, max_queue_size, sender_credentials):
        Outbox._set_flush_interval(flush_interval)
        Outbox._set_max_size(max_queue_size)
        Outbox._set_credentials(sender_credentials)
        Outbox.__stop_flush_thread = False
        Outbox.__smtp_error_occurred = False
        Outbox.__flush_thread = threading.Thread(
            target=Outbox._flush_thread, daemon=True
        )
        Outbox.__flush_thread.start()
        Outbox.__working = True

    @staticmethod
    def stop():
        if Outbox.__working is False:
            raise IllegalStopError("Outbox was not started")
        Outbox.__stop_flush_thread = True
        Outbox.__flush_thread.join()
        Outbox.__working = False

    @staticmethod
    def _flush_thread():
        while not Outbox.__stop_flush_thread:
            start_time = time.time()
            while time.time() - start_time < Outbox.__flush_interval:
                if Outbox._queue.qsize() == Outbox.__max__queue_size:
                    Outbox._flush_queue()
                time.sleep(10)
            if Outbox._queue.qsize() != 0:
                Outbox._flush_queue()

    @staticmethod
    def _flush_queue():
        Outbox._send_mails()

    @staticmethod
    def _send_mails(
        smtp_server="smtp.gmail.com",
        smtp_port=465,
    ):
        sender_email, email_password = (
            Outbox.__sender_credentials["email"],
            Outbox.__sender_credentials["password"],
        )

        try:
            with smtplib.SMTP_SSL(
                smtp_server, smtp_port, context=ssl.create_default_context()
            ) as email:
                email.login(sender_email, email_password)

                for _ in range(Outbox._queue.qsize()):
                    mail = Outbox._queue.get()
                    email_message = (
                        f"Subject:{mail['subject']}\nTo:{mail['to']}\n{mail['body']}"
                    )
                    receiver_mail = mail["to"]
                    # if the first time the mail is not sent, try once more
                    for _ in range(2):
                        try:
                            email.sendmail(sender_email, receiver_mail, email_message)
                            Outbox._keep_log(mail)  # keeps a record of the mails sent
                            break
                        except Exception:
                            continue
        except Exception:
            Outbox.__smtp_error_occurred = True
            # raise SmtpError(e)

    @staticmethod
    def _keep_log(mail_dict):
        copy_dict = mail_dict
        copy_dict["datetime"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        # Remove commas from the 'subject' key
        copy_dict["subject"] = copy_dict["subject"].replace(",", "")
        # Filter out key-value pairs related to 'body'
        copy_dict = {
            key: value for key, value in sorted(copy_dict.items()) if key != "body"
        }
        with open("mail_logs.csv", mode="a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=copy_dict.keys())

            # Check if the file is empty
            if file.tell() == 0:
                writer.writeheader()

            # Append the data row
            writer.writerow(copy_dict)

    @staticmethod
    def push(mail):
        Outbox._queue.put(mail)

    @staticmethod
    def size():
        return Outbox._queue.qsize()


def send_email(
    receiver_mail: str,
    message: str,
    sender_credentials: dict,
    subject: str,
    smtp_server="smtp.gmail.com",
    smtp_port=465,
):
    sender_email, email_password = (
        sender_credentials["email"],
        sender_credentials["password"],
    )

    email_message = f"Subject:{subject}\nTo:{receiver_mail}\n{message}"

    try:
        with smtplib.SMTP_SSL(
            smtp_server, smtp_port, context=ssl.create_default_context()
        ) as email:
            email.login(sender_email, email_password)
            email.sendmail(sender_email, receiver_mail, email_message)
    except Exception as e:
        raise e


class SmtpError(RuntimeError):
    pass


class IllegalStopError(RuntimeError):
    pass


"""
my_credentials = {'email': "tejaswin2608@gmail.com", 'password': "xxlabmkghfwfpnfm"}
try:
    Outbox.start(flush_interval=10, max_queue_size=10, sender_credentials=my_credentials)
except Exception as e: #imaplib.IMAP4.error as e: # invalid credentials
    print(e)
    raise e

while True:
    if Outbox.smtp_error_occurred():  #if this returns True, you must call Outbox.stop()
        break
    mail1 = {'subject': 'hey bud', 'to': 'vinnijammu18@gmail.com', 'body': 'Nice to meet you'}
    Outbox.push(mail1)
    mail2 = {'subject': 'Good morning', 'to': 'tejaswin04@gmail.com', 'body': 'Did you saw the sunrise today?'}
    Outbox.push(mail2)
    #time.sleep(10)

#print(Outbox.smtp_error_occurred)
Outbox.stop()
"""
