from urllib.parse import parse_qs

import aiohttp
import discord
from discord.ext import commands
from lxml import etree


class Google(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def parse_google_card(self, node):
        if node is None:
            return None

        e = discord.Embed(colour=0x738bd7)

        # check if it's a calculator card:
        calculator = node.find(".//table/tr/td/span[@class='nobr']/h2[@class='r']")
        if calculator is not None:
            e.title = 'Calculator'
            e.description = ''.join(calculator.itertext())
            return e

        parent = node.getparent()

        # check for unit conversion card
        unit = parent.find(".//ol//div[@class='_Tsb']")
        if unit is not None:
            e.title = 'Unit Conversion'
            e.description = ''.join(''.join(n.itertext()) for n in unit)
            return e

        # check for currency conversion card
        currency = parent.find(".//ol/table[@class='std _tLi']/tr/td/h2")
        if currency is not None:
            e.title = 'Currency Conversion'
            e.description = ''.join(currency.itertext())
            return e

        # check for release date card
        release = parent.find(".//div[@id='_vBb']")
        if release is not None:
            try:
                e.description = ''.join(release[0].itertext()).strip()
                e.title = ''.join(release[1].itertext()).strip()
                return e
            except:  # noqa
                return None

        # check for translation card
        words = parent.find(".//ol/div[@class='g']/div/table/tr/td/h3[@class='r']")
        if words is not None:
            e.title = 'Google Translate'
            e.add_field(name='Input', value=words[0].text, inline=True)
            e.add_field(name='Output', value=words[1].text, inline=True)
            return e

        # check for definition card
        words = parent.find(".//ol/div[@class='g']/div/h3[@class='r']/div")
        if words is not None:
            try:
                definition_info = words.getparent().getparent()[1]  # yikes
            except:  # noqa
                pass
            else:
                try:
                    # inside is a <div> with two <span>
                    # the first is the actual word, the second is the pronunciation
                    e.title = words[0].text
                    e.description = words[1].text
                except:  # noqa
                    return None

                # inside the table there's the actual definitions
                # they're separated as noun/verb/adjective with a list
                # of definitions
                for row in definition_info:
                    if len(row.attrib) != 0:
                        # definitions are empty <tr>
                        # if there is something in the <tr> then we're done
                        # with the definitions
                        break

                    try:
                        data = row[0]
                        lexical_category = data[0].text
                        body = []
                        for index, definition in enumerate(data[1], 1):
                            body.append('%s. %s' % (index, definition.text))

                        e.add_field(name=lexical_category, value='\n'.join(body), inline=False)
                    except:  # noqa
                        continue

                return e

        # check for "time in" card
        time_in = parent.find(".//ol//div[@class='_Tsb _HOb _Qeb']")
        if time_in is not None:
            try:
                time_place = ''.join(time_in.find("span[@class='_HOb _Qeb']").itertext()).strip()
                the_time = ''.join(time_in.find("div[@class='_rkc _Peb']").itertext()).strip()
                the_date = ''.join(time_in.find("div[@class='_HOb _Qeb']").itertext()).strip()
            except:  # noqa
                return None
            else:
                e.title = time_place
                e.description = '%s\n%s' % (the_time, the_date)
                return e

        # check for weather card
        # this one is the most complicated of the group lol
        # everything is under a <div class="e"> which has a
        # <h3>{{ weather for place }}</h3>
        # string, the rest is fucking table fuckery.
        weather = parent.find(".//ol//div[@class='e']")
        if weather is None:
            return None

        location = weather.find('h3')
        if location is None:
            return None

        e.title = ''.join(location.itertext())

        table = weather.find('table')
        if table is None:
            return None

        # This is gonna be a bit fucky.
        # So the part we care about is on the second data
        # column of the first tr
        try:
            tr = table[0]
            img = tr[0].find('img')
            category = img.get('alt')
            image = 'https:' + img.get('src')
            temperature = tr[1].xpath("./span[@class='wob_t']//text()")[0]
        except:  # noqa
            return None  # RIP
        else:
            e.set_thumbnail(url=image)
            e.description = '*%s*' % category
            e.add_field(name='Temperature', value=temperature)

        # On the 4th column it tells us our wind speeds
        try:
            wind = ''.join(table[3].itertext()).replace('Wind: ', '')
        except:  # noqa
            return None
        else:
            e.add_field(name='Wind', value=wind)

        # On the 5th column it tells us our humidity
        try:
            humidity = ''.join(table[4][0].itertext()).replace('Humidity: ', '')
        except:  # noqa
            return None
        else:
            e.add_field(name='Humidity', value=humidity)

        return e

    async def get_google_entries(self, query):
        params = {
            'q': query,
            'safe': 'on'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64)'
        }

        # list of URLs
        entries = []

        # the result of a google card, an embed
        card = None
        async with aiohttp.ClientSession() as cs:
            async with cs.get('https://www.google.com/search', params=params, headers=headers) as resp:
                if resp.status != 200:
                    link = "https://www.google.com/search?q=" + query.replace(" ", "+")
                    raise RuntimeError('Google decided to ignore the bot.\n'
                                       'Use the following link to achieve the same result:\n' + link)

                root = etree.fromstring(await resp.text(), etree.HTMLParser())

                # with open('google.html', 'w', encoding='utf-8') as f:
                #     f.write(etree.tostring(root, pretty_print=True).decode('utf-8'))

                """
                Tree looks like this.. sort of..
                <div class="g">
                    ...
                    <h3>
                        <a href="/url?q=<url>" ...>title</a>
                    </h3>
                    ...
                    <span class="st">
                        <span class="f">date here</span>
                        summary here, can contain <em>tag</em>
                    </span>
                </div>
                """

                card_node = root.find(".//div[@id='topstuff']")
                card = self.parse_google_card(card_node)

                search_nodes = root.findall(".//div[@class='g']")
                for node in search_nodes:
                    url_node = node.find('.//h3/a')
                    if url_node is None:
                        continue

                    url = url_node.attrib['href']
                    if not url.startswith('/url?'):
                        continue

                    url = parse_qs(url[5:])['q'][0]  # get the URL from ?q query string

                    # if I ever cared about the description, this is how
                    entries.append(url)

                    # short = node.find(".//span[@class='st']")
                    # if short is None:
                    #     entries.append((url, ''))
                    # else:
                    #     text = ''.join(short.itertext())
                    #     entries.append((url, text.replace('...', '')))

        return card, entries

    @commands.command(aliases=['google', 'search'])
    async def g(self, ctx, *, query):
        """Searches google and gives you top result."""
        await ctx.trigger_typing()
        try:
            card, entries = await self.get_google_entries(query)
        except RuntimeError as e:
            await ctx.send(str(e))
        else:
            if card:
                value = '\n'.join(entries[:3])
                if value:
                    card.add_field(name='Search Results', value=value, inline=False)
                return await ctx.send(embed=card)

            if len(entries) == 0:
                return await ctx.send('No results found... sorry.')

            icon = "https://cdn.discordapp.com/attachments/246291440106340352/293036111373139969/google_logo1600.png"
            emb = discord.Embed(colour=0x77EE00, timestamp=ctx.message.created_at)
            emb.set_author(name="Google Search", url="https://www.google.com/search?q=" + query.replace(" ", "+"),
                           icon_url=icon)
            next_two = entries[1:3]
            first_entry = entries[0]
            if first_entry[-1] == ')':
                first_entry = first_entry[:-1] + '%29'

            if next_two:
                formatted = '\n'.join(map(lambda x: '<%s>' % x, next_two))
                emb.add_field(name="Search Result", value=first_entry)
                emb.add_field(name="More", value=formatted, inline=False)
            else:
                emb.add_field(name="Search Result", value=first_entry)

            await ctx.send(embed=emb)


def setup(bot):
    bot.add_cog(Google(bot))
