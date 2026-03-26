from flask import Flask
from flask_mysqldb import MySQL

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for sessions

# MySQL configuration (from XAMPP)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'       # default XAMPP user
app.config['MYSQL_PASSWORD'] = ''       # default XAMPP password
app.config['MYSQL_DB'] = 'vastukalp_db' # the database you created

mysql = MySQL(app)