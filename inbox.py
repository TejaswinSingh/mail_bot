import threading
import time
from queue import Queue
import imaplib
import email
import ssl
from email.header import decode_header


class Inbox:
    _queue = Queue()
    __refill_interval = None
    __refill_thread = None
    __stop_refill_thread = False  # flag
    _imap = None
    __logged_in = False

    @staticmethod
    def _set_refill_interval(val):
        if not isinstance(val, int):
            raise TypeError(
                "start() method argument 'refill_interval' must be of type 'int'"
            )
        if val < 0:
            raise ValueError(
                "start() method argument 'refill_interval' must be a positive integer"
            )
        Inbox.__refill_interval = val

    @staticmethod
    def logged_in():
        return Inbox.__logged_in

    @staticmethod
    def start(refill_interval, username, password):
        Inbox._set_refill_interval(refill_interval)
        imap_server = "imap.gmail.com"
        context = ssl.create_default_context()
        port = 993
        try:
            Inbox._imap = imaplib.IMAP4_SSL(imap_server, port, ssl_context=context)
            Inbox._imap.login(username, password)
            Inbox.__logged_in = True
        except Exception as e:
            raise ImapError(e)
        Inbox.__stop_refill_thread = False
        # we must ensure that we have logged in to the IMAP server before starting the refill thread which in runs refill_queue (which gets mail from gmail)
        Inbox.__refill_thread = threading.Thread(
            target=Inbox._refill_thread, daemon=True
        )
        Inbox.__refill_thread.start()

    # must call this function when the Inbox is no longer used  otherwise the daemon thread will continue on running.
    @staticmethod
    def stop():
        if Inbox.__logged_in is False:
            raise IllegalImapLogoutError("User is not logged in")
        Inbox.__stop_refill_thread = True
        Inbox.__refill_thread.join()  # join the refill thread if you want it to finish its work before exiting. This ensures that even if the main thread calls it to stop, the refill thread wil stop only after finishing its work
        Inbox._imap.logout()
        Inbox.__logged_in = False

    # the _queue will refill itself whenever it becomes empty (to be exact it will refill itself under 5 sec of being empty)
    # More so, the _queue will also refill itself after every refill_interval seconds, regardless of whether it is empty or not
    @staticmethod
    def _refill_thread():
        while not Inbox.__stop_refill_thread:
            st = time.time()
            while time.time() - st < Inbox.__refill_interval:
                if Inbox._queue.qsize() == 0:
                    Inbox._refill_queue()
                time.sleep(5)  # increase this to put less pressure on the CPU
            Inbox._refill_queue()

    # refills the _queue with new unseen mails
    @staticmethod
    def _refill_queue():
        mail_ids = Inbox._fetch_new_mails()
        # error getting mails
        if mail_ids == None:
            return  # RuntimeError('Error getting mail')
        # no new mails found
        if mail_ids[0] == 0:
            return
        for mail_id in mail_ids[
            1
        ]:  # first element is just the number of mail_ids found
            try:
                mail_details = Inbox._get_mail_details(mail_id)
                # skip invalid mails with empty body/subject or with scam links
                if mail_details == None:
                    continue
                Inbox._queue.put(mail_details)
            # mails with pictures, graphics (auto-generated / marketing mails) give decoding error, so skip them
            except Exception:
                continue

    @staticmethod
    # searches for new, unseen emails in the INBOX
    def _fetch_new_mails():
        # we will return this list, containing the number of unseen mails found as first element
        # and a nested list of ID's of all unseen emails found (if any) as the second element
        mail_ids = []

        # select a mailbox
        Inbox._imap.select("INBOX")  # use imap.list() see all the available mailboxes

        # Search for new/unseen emails
        status, email_ids = Inbox._imap.search(None, "UNSEEN")
        if status == "OK":
            email_ids = email_ids[0].split()
            num_unseen = len(email_ids)
            mail_ids.append(num_unseen)

            if (
                num_unseen == 0
            ):  # return a single element list with only 0 if no unseen mails found
                return mail_ids

            mail_ids.append(email_ids)
            return mail_ids

        else:  # if status is not 'OK', return None to signal
            return None

    @staticmethod
    # return a dict in the format {'subject':str, 'sender':str, 'body':str} with the email details
    def _get_mail_details(email_id):
        details = {"subject": None, "sender": None, "body": None}
        # fetch the email message by ID
        res, msg = Inbox._imap.fetch(email_id, "(RFC822)")  # res is unused here
        for response in msg:
            if isinstance(response, tuple):
                # parse a bytes email into a message object
                msg = email.message_from_bytes(response[1])
                # decode the email subject
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    # if it's a bytes, decode to str
                    subject = subject.decode(encoding)
                details["subject"] = subject

                # skip mails with empty subject
                if details["subject"].strip() == "":
                    return None

                # decode email sender
                sender, encoding = decode_header(msg.get("From"))[0]
                if isinstance(sender, bytes):
                    sender = sender.decode(encoding)
                details["sender"] = sender
                # if the email message is multipart
                if msg.is_multipart():
                    # iterate over email parts
                    for part in msg.walk():
                        # extract content type of email
                        content_type = part.get_content_type()
                        try:
                            # get the email body
                            body = part.get_payload(decode=True).decode()
                        except:
                            pass
                        if content_type == "text/plain":
                            details["body"] = body
                else:
                    # extract content type of email
                    content_type = msg.get_content_type()
                    # get the email body
                    body = msg.get_payload(decode=True).decode()
                    if content_type == "text/plain":
                        details["body"] = body

        # skip mails with empty body or with scam links
        if (
            details["body"].strip() == ""
            or "http" in details["body"]
            or "https" in details["body"]
        ):
            return None

        return details

    @staticmethod
    def pop():
        if Inbox._queue.empty():
            return None
        return Inbox._queue.get()

    @staticmethod
    def size():
        return Inbox._queue.qsize()


class ImapError(RuntimeError):
    pass


class IllegalImapLogoutError(RuntimeError):
    pass


"""
try:
    Inbox.start(refill_interval=100, username='tejaswin2608@gmail.com', password='xxlabmkghfwfpnfm')
except Exception as e: #imaplib.IMAP4.error as e: # invalid credentials
    print(e)
    raise e
while True:
    try:
        user = int(input("enter: "))
        match user:
            case 0:
                print(Inbox.size())
            case 1:
                print(Inbox.pop())
            case 2:
                print('exiting')
                break
    except Exception:
        break 
Inbox.stop()  """
