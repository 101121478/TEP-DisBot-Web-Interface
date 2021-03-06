import os
import mysql.connector
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

from flask import Flask, render_template, redirect, url_for, request
from flask_discord import DiscordOAuth2Session, Unauthorized, AccessDenied


# Get SQL database details
dbHost = os.getenv('dbHost')
dbUser = os.getenv('dbUser')
dbPassword = os.getenv('dbPassword')
db = os.getenv('database')

app = Flask(__name__)

app.secret_key = b"%\xe0'\x01\xdeH\x8e\x85m|\xb3\xffCN\xc9g"
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"  

app.config["DISCORD_CLIENT_ID"] = os.getenv('CLIENT_ID')
app.config["DISCORD_CLIENT_SECRET"] = os.getenv('CLIENT_SECRET')
app.config["DISCORD_BOT_TOKEN"] = os.getenv('BOT_TOKEN')
app.config["DISCORD_REDIRECT_URI"] = "https://tep-disbot-web-interface.herokuapp.com/callback"

discord = DiscordOAuth2Session(app)

# Check if user is an administrator
# Used to verify user is allowed to login to web interface.
def isUserAdmin():
    user_guilds = discord.fetch_guilds()

    institute_server_id = 819751859945996300

    if user_guilds:
        for guild in user_guilds:
            if guild.id == institute_server_id:
                if guild.permissions.administrator:
                    return True
    return False

# Check if user is authorised and an admin
# Used if used attempts to access page via url
def isAuthorisedAndAdmin():
    if isUserAdmin():
        if discord.authorized:
            return True

    return False



#Initial page that is displayed when accessing web interface
@app.route("/")
def index():
    if not discord.authorized:
        return render_template("login.html")

    user = discord.fetch_user()

    if isUserAdmin():
        templateData = {
            'user'   : user,
            }
        return render_template("index.html", **templateData)
    raise Unauthorized



#Catches any 'Unathorized' errors that are thrown. Redirects to index.html.
@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return render_template('login.html', errorText="User not authorized or hasn't logged in. Only Administrators are authorised to access.")


#Catches any 'AccessDenied' errors that are thrown. Redirects to index.html.
@app.errorhandler(AccessDenied)
def redirect_unauthorized(e):
    return render_template('login.html', errorText="Access Denied")


# Login page which creates the discord session for the user login.
@app.route("/login/")
def login():
    return discord.create_session()


# Executes when the user logs in discord's OAuth returns back to the web interface
@app.route("/callback/")
def callback():
    data = discord.callback()
    redirect_to = data.get("redirect", "/")
    
    return redirect(redirect_to)


# Executes when user clicks add topic/concept button on index page. Displays simple text input form to enter topic/concept.
@app.route("/addTopic/")
def displayAddTopicForm():
    if not isAuthorisedAndAdmin():
        return redirect(url_for('index'))

    return render_template('addTopic.html')


# Executes when the user submits the form on addTopic page. Submits to itself via POST and topic/concept is added to topics table.
@app.route("/addTopic/", methods=['POST'])
def recieveAddTopicForm():
    if not isAuthorisedAndAdmin():
        return redirect(url_for('index'))

    topic = request.form['topic']

    if topic == "":
        return render_template('deleteTopic.html', output="No topic entered!")
    else:
        # Initialise connection to SQL database with details from .env file
        mydb = mysql.connector.connect(
            host=dbHost,
            user=dbUser,
            password=dbPassword,
            database=db
        )
        mycursor = mydb.cursor()

        topic = topic.lower()
        sql = "SELECT * FROM topics WHERE topic = '{}'".format(topic)

        mycursor.execute(sql)
        result = mycursor.fetchall()

        if result:
            output="Topic/Concept: '{}' already exists in topics table in database: {}.".format(topic, db)
            return render_template('addTopic.html', output=output)
        else:
            sql = "INSERT INTO topics (topic, count) VALUES (%s, %s)"
            val = (topic, 0)
            
            mycursor.execute(sql, val)
            mydb.commit()

            output="Added topic/concept: '{}' to the topics table in database: {}.".format(topic, db)
            return render_template('addTopic.html', output=output)


# Executes when user clicks delete topic/concept button on index page. Displays simple text input form to enter topic/concept.
@app.route("/deleteTopic/")
def displayDeleteTopicForm():
    if not isAuthorisedAndAdmin():
        return redirect(url_for('index'))

    return render_template('deleteTopic.html')


# Executes when the user submits the form on deleteTopic page. Submits to itself via POST and topic/concept is deleted from topics table.
@app.route("/deleteTopic/", methods=['POST'])
def recieveDeleteTopicForm():
    if not isAuthorisedAndAdmin():
        return redirect(url_for('index'))

    topic = request.form['topic']

    if topic == "":
        return render_template('deleteTopic.html', output="No topic entered!")
    else:
        # Initialise connection to SQL database with details from .env file
        mydb = mysql.connector.connect(
            host=dbHost,
            user=dbUser,
            password=dbPassword,
            database=db
        )
        mycursor = mydb.cursor()

        topic = topic.lower()
        sql = "SELECT * FROM topics WHERE topic = '{}'".format(topic)

        mycursor.execute(sql)
        result = mycursor.fetchall()

        if not result:
            output="No topic/concept: '{}' in topics table in database: {}.".format(topic, db)
            return render_template('deleteTopic.html', output=output)
        else:
            sql = "DELETE FROM topics WHERE topic = '{}'".format(topic)

            mycursor.execute(sql)
            mydb.commit()

            output="Topic/Concept: '{}' has been deleted from topics table in database: {}.".format(topic, db)
            return render_template('deleteTopic.html', output=output)


#HTML page for displaying the topics SQL table 
@app.route('/displayTopics/')
def displayTopics():
    if not isAuthorisedAndAdmin():
        return redirect(url_for('index'))
    
    topics = []
    counts = []

    # Initialise connection to SQL database with details from .env file
    mydb = mysql.connector.connect(
        host=dbHost,
        user=dbUser,
        password=dbPassword,
        database=db
    )

    with mydb:
        cursor = mydb.cursor()
        cursor.execute("SELECT * FROM topics ORDER BY count DESC")
        results = cursor.fetchall()

    for row in results:
        topics.append(row[0])
        counts.append(row[1])

    topicsGraph = build_barGraph(topics, counts, 'Topics/Concept', 'Count', 'Number of times Topics/Concepts have been discussed')
        
    templateData = {
        'topics' : results,
        'graph'  : topicsGraph
        }
    return render_template('displayTopics.html', **templateData)


#HTML page for displaying the strikes SQL table 
@app.route('/displayStrikes/')
def displayStrikes():
    if not isAuthorisedAndAdmin():
        return redirect(url_for('index'))

    users = []
    strikes = []

    # Initialise connection to SQL database with details from .env file
    mydb = mysql.connector.connect(
        host=dbHost,
        user=dbUser,
        password=dbPassword,
        database=db
    )

    with mydb:
        cursor = mydb.cursor()
        cursor.execute("SELECT * FROM strikes ORDER BY count DESC")
        results = cursor.fetchall()
    
    for row in results:
        users.append(row[0])
        strikes.append(row[1])

    strikesGraph = build_barGraph(users, strikes, 'Member', 'Strikes', 'Users and the number of strikes they have')

    templateData = {
        'rows' : results,
        'graph'  : strikesGraph
        }

    return render_template('displayStrikes.html', **templateData)

# Builds a bar graph using the data, headings and title provided
def build_barGraph(x, y, xlabel, ylabel, title):
    plt.clf()

    img = io.BytesIO()

    plt.bar(x,y)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.savefig(img, format='png')
    img.seek(0)

    plot_url = base64.b64encode(img.getvalue()).decode()

    return 'data:image/png;base64,{}'.format(plot_url)

# Executes when the user presses the logout button in index.html
@app.route("/logout/")
def logout():
    discord.revoke()
    return redirect(url_for(".index"))