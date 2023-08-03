# Discord Imports
from discord.ext import commands
import discord

# SQL Imports
import pymysql
from pymysql.err import MySQLError

# Time Imports
from datetime import datetime
import pytz


# Database connection variables
DB_HOST = 'eu-cdbr-west-02.cleardb.net'
DB_USER = 'be3ad188270142'
DB_PASS = 'a8b123a0'
DB = 'heroku_708e83ea7f67b93'

def GetLogsChannelIdByServerId(serverid, dbCursor):
    dbCursor.execute(f"SELECT * FROM `servers_info`")
    results = dbCursor.fetchall()
    
    for res in results:
        if res['server_id'] == serverid:
            if res['server_logs_chan_id'] == "Default":
                return 0
            else:
                return res['server_logs_chan_id']

    return 0

async def log(logChan, *text):
    # Getting current time
    timezone = pytz.timezone('Europe/Vilnius')
    now = datetime.now(timezone)
    current_time = now.strftime("%H:%M:%S")

    # Getting channel object
    logChan = bot.get_channel(logChan)

    # Joining args (text)
    text = ' '.join(text)

    # Sending message to logs channel
    await logChan.send(f"[{current_time}] {text}")

def CheckIfTicketRepetitive(guildid, userid, type):
    # Opening connection
    connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # Checking if user with specified ticket type already exists in database
    cursor.execute(f"SELECT * FROM `ticket_owners`")
    results = cursor.fetchall()
    for res in results:
        if(res["server_id"] == str(guildid) and res["ticket_owner_id"] == str(userid)):
            if(type in res['ticket_name']):
                return True
    return False

def RegisterSevrerOnDatabase(guild):
    # Opening connection
    connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
    cursor = connection.cursor(pymysql.cursors.DictCursor)
    
    # Storing `servers_info` table into results variable
    cursor.execute(f"SELECT * FROM `servers_info`")
    results = cursor.fetchall()

    # Checking if server already exists on database
    for res in results:
        if(res["server_id"] == str(guild.id)):
            connection.close()
            return
    
    # Insert new server into the database
    sql=f"""INSERT INTO `servers_info`(server_name, server_id)
        VALUES (%s, %s)"""
    val = (guild.name, guild.id)
    cursor.execute(sql, val)
    connection.commit()
    print(f"Server {guild.name} has been successfully registered on database.")

    # Closing connection
    connection.close()

async def CreateTicket(guild, type, user):

    
    # Opening connection
    connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # Storing `servers_info` table into results variable
    cursor.execute(f"SELECT * FROM `servers_info`")
    results = cursor.fetchall()

    # Getting server vars, and checking if required ones are specified or not
    for res in results:
        if(res["server_id"] == str(guild.id)):
            ticket_id = res["server_ticket_id"]
            

            if int(res['server_blistrole_id']) in [y.id for y in user.roles]:
                print(f"Access for calling a ticket for user {user.name} has been denied. (Blacklisted)")
                return



            if(res['server_tickets_cat_id']=="Default" or res['server_logs_chan_id'] == "Default"):
                print(f"Error. Not all vars have been set yet. {guild.name}")
                return
            else:
                tickets_cat_id = int(res["server_tickets_cat_id"])
                await log(int(res['server_logs_chan_id']), f"🔹 User **{user.display_name}** created a ticket **{type}-{ticket_id}**")
            break
    

    # Creating ticket channel and sending greet message to it
    overwrites = {
    guild.default_role: discord.PermissionOverwrite(read_messages=False),
    guild.me: discord.PermissionOverwrite(read_messages=True),
    user: discord.PermissionOverwrite(read_messages=True)
    }
    channel = await guild.create_text_channel(f'{type}-{ticket_id}', category=discord.utils.get(guild.categories, id=tickets_cat_id), overwrites=overwrites)
    await channel.send("```Hello! Please wait while our team is assisting other people. We will take care of your wishes as soon as possible. Estimated time of response: from 5 minutes to 4 hours.```", view=InsideTicketFormat())

    # Increasing ticket index by one in the database
    cursor.execute(f"UPDATE `servers_info` SET `server_ticket_id` = %s WHERE `server_id` = %s", (ticket_id+1, guild.id))
    connection.commit()

    # Inserting ticket information into the database
    sql=f"INSERT INTO `ticket_owners`(server_name, ticket_owner_name, ticket_name, server_id, ticket_chan_id, ticket_owner_id) VALUES (%s, %s, %s, %s, %s, %s)"
    val = (str(guild.name), str(user.name), str(channel.name), str(guild.id), str(channel.id), str(user.id))
    cursor.execute(sql, val)
    connection.commit()

    # Closing connection
    connection.close()

async def CloseTicket(guild, channel, admin):

    # Opening connection
    connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # Storing `ticket_owners` table into results variable
    cursor.execute(f"SELECT * FROM `ticket_owners`")
    results = cursor.fetchall()

    # Searching for ticket owner in specific server
    for res in results:
        if res['server_id'] == str(guild.id) and res['ticket_chan_id'] == str(channel.id):

            # Logging
            logs_chan_id = GetLogsChannelIdByServerId(res['server_id'], cursor)
            if(not logs_chan_id):
                print(f"Error. Not all vars have been set yet. {guild.name}")
                return

            await log(int(logs_chan_id), f"🔸 Administrator **{admin.name}** closed user's **{res['ticket_owner_name']}** ticket called **{res['ticket_name']}**")

            # Deleting ticket channel
            await channel.delete()

            # Deleting ticket from database
            cursor.execute(f"DELETE FROM ticket_owners WHERE `server_id` = %s AND `ticket_chan_id` = %s", (res['server_id'], res['ticket_chan_id']))
            connection.commit()


            # Sending DM
            user = await bot.fetch_user(int(res['ticket_owner_id']))
            await user.send(f"Your ticket **{res['ticket_name']}** in server **{res['server_name']}** has been closed by an administrator **{admin.display_name}**.")
    
    # Closing connection
    connection.close()

def Setups(guild):
    # Opening connection
    connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # Primary value which will be supplemented later
    setups = "```"

    # Storing `servers_info` table into results variable
    cursor.execute(f"SELECT * FROM `servers_info`")
    results = cursor.fetchall()
    connection.close()

    # Getting through every server, and if server is
    # required, supplementing setup variable with current
    # esablished vars in databsae
    for res in results:
        if res['server_id'] == str(guild.id):
            setups += f"Server ticket category ({res['server_cmd_prefix']}setupticketcatid [category id]): "
            setups += res['server_tickets_cat_id'] + "\n"

            setups += f"Server console channel id ({res['server_cmd_prefix']}setupconsolechannel [channel tag]): "
            setups += res['server_console_chan_id'] + "\n"

            setups += f"Server logs channel id ({res['server_cmd_prefix']}setuplogschannel [channel tag]): "
            setups += res['server_logs_chan_id'] + "\n"
            
            setups += f"Server blist role id ({res['server_cmd_prefix']}setupblistroleid [role id]): "
            setups += res['server_blistrole_id'] + "\n"

            setups += f"Server admin role id ({res['server_cmd_prefix']}setupadminroleid [role id]): "
            setups += res['server_adminrole_id'] + "\n"
            setups += "```"

    return setups

# Defining "view", how buttons will look on message inside ticket, and what they will do
class InsideTicketFormat(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Close', style=discord.ButtonStyle.danger, emoji="🔐", custom_id='persistent_view:close')
    async def close(self, button: discord.ui.Button, interaction: discord.Interaction):
        if(interaction.user.guild_permissions.administrator):
            await CloseTicket(interaction.guild, interaction.channel, interaction.user)
            await interaction.response.defer()
        else:
            await interaction.response.send_message("Tickets can be closed by administrators only.", ephemeral=True)

# Defining "view", how buttons will look on request ticket message, and what they will do
class TicketFormat(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Purchase', style=discord.ButtonStyle.green, emoji="🛒", custom_id='persistent_view:purchase')
    async def purchase(self, button: discord.ui.Button, interaction: discord.Interaction):


        if CheckIfTicketRepetitive(interaction.guild.id, interaction.user.id, "purchase"):
            await interaction.response.send_message("You already have opened that type of ticket.", ephemeral=True)
        else:
            await CreateTicket(interaction.guild, "purchase", interaction.user)
            await interaction.response.defer()

    @discord.ui.button(label='Support', style=discord.ButtonStyle.red, emoji="📞", custom_id='persistent_view:support')
    async def support(self, button: discord.ui.Button, interaction: discord.Interaction):
        if CheckIfTicketRepetitive(interaction.guild.id, interaction.user.id, "support"):
            await interaction.response.send_message("You already have opened that type of ticket.", ephemeral=True)
        else:
            await CreateTicket(interaction.guild, "support", interaction.user)
            await interaction.response.defer()

    @discord.ui.button(label='Parnership', style=discord.ButtonStyle.grey, emoji="🤝", custom_id='persistent_view:partnership')
    async def parnership(self, button: discord.ui.Button, interaction: discord.Interaction):
        if CheckIfTicketRepetitive(interaction.guild.id, interaction.user.id, "parnership"):
            await interaction.response.send_message("You already have opened that type of ticket.", ephemeral=True)
        else:
            await CreateTicket(interaction.guild, "parnership", interaction.user)
            await interaction.response.defer()

class VerificationFormat(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Close', style=discord.ButtonStyle.danger, emoji="🔐", custom_id='persistent_view:close')
    async def close(self, button: discord.ui.Button, interaction: discord.Interaction):
        if(interaction.user.guild_permissions.administrator):
            await CloseTicket(interaction.guild, interaction.channel, interaction.user)
            await interaction.response.defer()
        else:
            await interaction.response.send_message("Tickets can be closed by administrators only.", ephemeral=True)



# Establishing bot vars, handling events
class PersistentViewBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents().all()
        activity = discord.Game(name="https://discord.gg/U7t4cJzWfc")

        super().__init__(command_prefix=('!'), intents=intents, activity=activity)

    async def setup_hook(self) -> None:
        self.add_view(TicketFormat())
        self.add_view(InsideTicketFormat())

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')

    async def on_guild_join(self, guild):
        RegisterSevrerOnDatabase(guild)

# Setting up bot var by previously established parameters
bot = PersistentViewBot()







# ######################## Setup Commands ########################
@bot.command()
@commands.is_owner()
async def setupticketmessage(ctx: commands.Context):
    await ctx.send("**Choose a ticket topic**", view=TicketFormat())

@bot.command()
@commands.has_permissions(administrator = True)
async def setupticketcatid(ctx: commands.Context, tickets_cat_id):
    if len(tickets_cat_id) == 18 and tickets_cat_id.isdigit():
        connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
        cursor = connection.cursor()
        cursor.execute(f"UPDATE `servers_info` SET `server_tickets_cat_id` = %s WHERE `server_id` = %s", (tickets_cat_id, str(ctx.guild.id)))
        connection.commit()
        connection.close()
        cat = bot.get_channel(int(tickets_cat_id))
        await ctx.send(f"Ticket category has been successfully set up. (**{cat.name}**)\n {Setups(ctx.guild)}")
    else:
        await ctx.send("Wrong format. Category id consists of 18 digits.")
        return

@bot.command()
@commands.has_permissions(administrator = True)
async def setupconsolechannel(ctx: commands.Context, channel: discord.TextChannel):
    chanid = channel.id
    connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
    cursor = connection.cursor()
    cursor.execute(f"UPDATE `servers_info` SET `server_console_chan_id` = %s WHERE `server_id` = %s", (str(chanid), str(ctx.guild.id)))
    connection.commit()
    connection.close()

    await ctx.send(f"Console channel has been successfully set up. (**{channel.mention}**)\n {Setups(ctx.guild)}")


@bot.command()
@commands.has_permissions(administrator = True)
async def setuplogschannel(ctx: commands.Context, channel: discord.TextChannel):
    chanid = channel.id
    connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
    cursor = connection.cursor()
    cursor.execute(f"UPDATE `servers_info` SET `server_logs_chan_id` = %s WHERE `server_id` = %s", (str(chanid), str(ctx.guild.id)))
    connection.commit()
    connection.close()

    await ctx.send(f"Logs channel has been successfully set up. (**{channel.mention}**)\n {Setups(ctx.guild)}")

@bot.command()
@commands.has_permissions(administrator = True)
async def setupblistroleid(ctx: commands.Context, roleid):
    if len(roleid) == 18 and roleid.isdigit():
        connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
        cursor = connection.cursor()
        cursor.execute(f"UPDATE `servers_info` SET `server_blistrole_id` = %s WHERE `server_id` = %s", (roleid, str(ctx.guild.id)))
        connection.commit()
        connection.close()
        
        role = ctx.guild.get_role(int(roleid))
        await ctx.send(f"Blist role has been successfully set up. (**{role.mention}**)\n {Setups(ctx.guild)}")

    else:
        await ctx.send("Wrong format. Category id consists of 18 digits.")
        return

@bot.command()
@commands.has_permissions(administrator = True)
async def setupadminroleid(ctx: commands.Context, roleid):
    if len(roleid) == 18 and roleid.isdigit():
        connection = pymysql.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASS, db=DB)
        cursor = connection.cursor()
        cursor.execute(f"UPDATE `servers_info` SET `server_adminrole_id` = %s WHERE `server_id` = %s", (roleid, str(ctx.guild.id)))
        connection.commit()
        connection.close()
        
        role = ctx.guild.get_role(int(roleid))

        await ctx.send(f"Admin role has been successfully set up. (**{role.mention}**)\n {Setups(ctx.guild)}")

    else:
        await ctx.send("Wrong format. Category id consists of 18 digits.")
        return


# Verification setups


@bot.command()
@commands.has_permissions(administrator = True)
async def setuphelp(ctx: commands.Context):
    await ctx.send(Setups(ctx.guild))




bot.run('OTI3Njg1NjM1MjQwNzcxNjQ1.YdN0kw.Bo0Sy_7EJcyU3m1CbAaV7m91wLI')