from inbox import Inbox
import inbox
from outbox import Outbox
import outbox
import gpt_scraper
import time
import re
import sys
import csv
from datetime import datetime
import spam_detection

responseBot = None
credentials = {}


# gets user credentials from the file - credentials.csv, present in the same directory
def read_credentials():
    with open("credentials.csv", "r") as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            credentials.update(row)


# prepares the responseBot so that it is ready to take queries
def set_bot():
    global responseBot
    responseBot = gpt_scraper.ChatGPT(
        hidden=True
    )  # set hidden to True to run chromeDriver in headless mode

    # login to ChatGPT
    my_openai_credentails = {
        "email": credentials["openai_email"],
        "password": credentials["openai_password"],
    }
    responseBot.set_credentials(
        my_openai_credentails["email"], my_openai_credentails["password"]
    )
    try:
        responseBot.login()
        return
    except TimeoutError as e:  # if a button/web-element was not found, try again
        raise RuntimeError(e)
    except (
        gpt_scraper.InvalidCredentialsError
    ) as e:  # if openai_credentials were not valid, raise error immediately
        raise RuntimeError(e)


# used to logout from the chatGPT website
def bot_logout():
    global responseBot
    if responseBot.logged_in():
        try:
            responseBot.logout(clear_chats=True)
        except TimeoutError:  # error clearing chats, rest is fine
            pass


# sets INBOX and OUTBOX
def set_mail_boxes():
    my_gmail_credentials = {
        "email": credentials["gmail"],
        "password": credentials["gmail_password"],
    }
    # set up the INBOX
    try:
        # refill_interval is used to set the loop interval after which the Inbox refills itself with new mails
        Inbox.start(
            refill_interval=30,
            username=my_gmail_credentials["email"],
            password=my_gmail_credentials["password"],
        )
    except inbox.ImapError as e:
        raise RuntimeError(e)  # bot cannot run if we can't login to IMAP

    # set up the OUTBOX
    # no need to catch any exception here
    # 'flush_interval' is used to set the interval after which the Outbox flushes/sends the mails inside of it
    # However, if the Outbox reaches 'max_queue_size', it flushes the mails out even though the flush_interval is not reached
    Outbox.start(
        flush_interval=30, max_queue_size=5, sender_credentials=my_gmail_credentials
    )


# this functin runs the whole script
def run(RUNTIME=(6 * 60 * 60)):
    # * first we set the bot and the mail boes
    # * INBOX is running on another thread of the CPU and is continously checking for any new mails, which if found are added to its queue
    # * Now we will dequeue these mails one by one from the INBOX, send a query to the bot, get the reponse, format it and then enqueue it to the OUTBOX's queue. This all is happening in the main thread
    # * Similar to the INBOX, the OUTBOX is also working on its own thread. It constantly checks its queue for any mails, and periodicly flushes them out to the respective receivers

    try:
        set_bot()
        set_mail_boxes()
    except RuntimeError as e:
        raise e

    # get base prompt
    with open("base_prompt.txt", "r") as file:
        base_prompt = file.read()

    global responseBot
    spam_filter = spam_detection.Spam_Detection_Model()

    # we will continue to check for new mails until RUNTIME
    start_time = time.time()
    while time.time() - start_time < RUNTIME:
        # if unable to login to Outbox (needs to be catched here via a flag beacuse this exception occurs in the flush_thread)
        if Outbox.smtp_error_occurred():
            # shutdown('Outbox - SMTP error occured')
            raise RuntimeError("Outbox - SMTP error occured")

        # get mail from Inbox
        mail = Inbox.pop()
        if mail == None:  # if Inbox is empty
            time.sleep(2)
            continue
        if credentials["gmail"] in mail["sender"]:  # don't reply to your own emails
            continue

        # pass the mail through spam filter
        if spam_filter.classify(mail["subject"]) == "spam":
            # print('spam skipped')
            continue

        # prepare prompt
        mail_body = f'From: {mail["sender"]}\n'
        mail_body += f'Subject: {mail["subject"]}\n'
        mail_body += mail["body"]

        prompt = base_prompt + mail_body

        # keep querying until the reply is given in proper format
        while True:
            # try to get a response from the bot, shutdown if no reponse was given after 5 tries
            response = ""
            for _ in range(5):
                error = ""
                try:
                    # ask query to ChatGPT
                    response = responseBot.query(prompt)
                    break

                except (
                    gpt_scraper.HourlyLimitReachedError
                ) as e:  # freeze the whole bot for half an hour, restart the bot and then try again. If still gives error, shutdown
                    error = e
                    freeze(30 * 60)  # 30 mins
                    try:
                        set_bot()
                        set_mail_boxes()
                        continue
                    except RuntimeError as e:
                        raise e
                except (
                    gpt_scraper.PromptTooLongError
                ):  # if prompt is too long, then skip this prompt/mail (though you need to logout of gpt and relogin first)
                    try:
                        bot_logout()
                        set_bot()
                        break  # gets the next mail
                    except RuntimeError as e:
                        raise e
                except (
                    gpt_scraper.MultiplePromptsError
                ) as e:  # if someone else is using your chatGPT account, logout, sleep for 5 mins, relogin and try again (max 5 times)
                    error = e
                    try:
                        bot_logout()
                        time.sleep(5 * 60)
                        set_bot()
                        continue
                    except RuntimeError as e:
                        raise e
                except (
                    TimeoutError
                ) as e:  # if a button/web-element was not found, try again
                    error = e
                    time.sleep(1)
                    continue
                except RuntimeError as e:  # if some unkown error occurs, shutdowm
                    raise e

            # if couldn't get a response even after trying 5 times, raise Runtime error
            if error != "":
                raise RuntimeError(error)

            # this handles the break from PromptTooLongError (because it doen't changes str 'error', so we catch it by looking at response)
            if response == "":
                break

            # Extracting subject from the response
            subject_match = re.search(r"Subject:(.+)", response)
            reply_subject = subject_match.group(1) if subject_match else ""

            # Extracting body from the response
            body_match = re.search(r"Body:(.+)", response, re.DOTALL)
            reply_body = body_match.group(1) if body_match else ""

            # continue asking chatgpt for a response, until it gives one in the proper format
            if reply_subject == "" or reply_body == "":
                continue

            # prepare and send the reply to the original sender
            reply_mail = {
                "to": mail["sender"],
                "subject": reply_subject,
                "body": reply_body,
            }
            Outbox.push(reply_mail)
            break  # gets the next mail


# logs out of all the places and then freezes the bot for the time specified - used for restart
def freeze(sleep_time):
    global responseBot

    if Inbox.logged_in():
        Inbox.stop()
    if Outbox.is_working():
        Outbox.stop()
    if responseBot.logged_in():
        try:
            responseBot.logout(clear_chats=True)
        except TimeoutError:  # error clearing chats
            pass

    time.sleep(sleep_time)


# called when bot needs to be stopped
# sends me an email whenever a shutdown occurs, also keeps track of all the shutdowns in the 'LogFile.txt'
def shutdown(message):
    global responseBot
    if message.strip() == "":
        message = "Reason- Undetermined Error"
    else:
        message = "Reason- " + message

    if Inbox.logged_in():
        Inbox.stop()
    if Outbox.is_working():
        Outbox.stop()
    try:
        if responseBot.logged_in():
            responseBot.logout(clear_chats=True)
    except (
        Exception
    ) as e:  # trouble clearing chats - runtime error, or attribute error if we try to shutdown before the responseBot was initialized
        message = f"[Unable to clear chats - {e}] " + message

    # let the user now that bot has stopped working via a mail and also keep shutdown records in a log file
    subject = "YOUR EMAIL BOT HAS STOPPED WORKING - ACTION REQUIRED!!!"
    try:
        outbox.send_email(
            credentials["shutdown_report_mail"],
            message[:125],
            {"email": credentials["gmail"], "password": credentials["gmail_password"]},
            subject,
        )  # the msg should not be longer than 125 characters
    except Exception:
        message = "[No mail was sent] " + message
    with open("LogFile.txt", "a") as file:
        file.write(f"[{datetime.now()}] >> {message}\n\n")

    sys.exit()


try:
    read_credentials()
    while True:
        run(RUNTIME=(3 * 60 * 60))  # we restart the bot every 3 hours
        freeze(10)
except KeyboardInterrupt as e:
    shutdown(str(e))
except Exception as e:
    shutdown(str(e))