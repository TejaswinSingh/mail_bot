import gpt_scraper

bot = gpt_scraper.ChatGPT(hidden=True)
bot.set_credentials('vinnijammu18@gmail.com', 'jaka1Rarotke@')

bot.login()

while True:
    question = input('enter: ')
    if question == "break":
        break
    reply = bot.query(question)
    print()
    print(reply)
    print('_____________________________________________________________________')
    print('\n')

bot.logout(clear_chats=True)