import os
import discord
from discord.ext.commands import Bot



TOKEN = os.environ.get("BOT_TOKEN")
extensions = ["roll", "roles", "utils", "search"]
startup_extensions = ["Cogs." + extension for extension in extensions]


class SynBot(Bot):
    def __init__(self):
        super().__init__(command_prefix=["syn ", "s!"], description="Misc Bot", game=discord.Game(name="s!help | syn help"))

    async def on_ready(self):
        print('Logged in!')
        print(self.user.name)
        print(self.user.id)
        print('------')
        print("Cogs loaded:")
        for extension in startup_extensions:
            try:
                self.load_extension(str(extension))
                print('"%s" loaded successfully' % extension.split(".")[1])
            except Exception as e:
                exc = '{}: {}'.format(type(e).__name__, e)
                print('Failed to load extension {}\n{}'.format(extension, exc))
        print('------')

SynBot().run(TOKEN)
