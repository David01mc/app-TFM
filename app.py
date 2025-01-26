from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = '8228.12349876'  # Cambia esto por algo único y seguro

# Configuración de la base de datos MongoDB
client = MongoClient("mongodb+srv://david01mc:1234TFM.@tfm-cluster.lrhnd.mongodb.net/?retryWrites=true&w=majority&appName=TFM-Cluster")  # Cambia la URL si tu MongoDB tiene otra configuración
db = client['chat_logs_db']
users_collection = db['users']

# Ruta principal (página de login o registro)
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form['action']
        username = request.form['username']
        password = request.form['password']

        if action == 'register':
            # Verificar si el usuario ya existe
            existing_user = users_collection.find_one({'username': username})
            if existing_user:
                flash('El nombre de usuario ya está registrado. Intente con otro.')
                return redirect(url_for('login'))

            # Encriptar la contraseña antes de guardarla
            hashed_password = generate_password_hash(password)
            
            # Guardar usuario y contraseña en MongoDB
            users_collection.insert_one({'username': username, 'password': hashed_password})

            flash('Usuario registrado con éxito.')
            return redirect(url_for('login'))

        elif action == 'login':
            # Buscar usuario en la base de datos
            user = users_collection.find_one({'username': username})
            if user and check_password_hash(user['password'], password):
                return redirect(url_for('welcome', username=username))
            else:
                flash('Usuario o contraseña incorrectos.')

    return render_template('login.html')

# Ruta de bienvenida después de loguearse
@app.route('/welcome/<username>')
def welcome(username):
    return f"<h1>Bienvenido, {username}!</h1>"

if __name__ == '__main__':
    app.run(debug=True)
