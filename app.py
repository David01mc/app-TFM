from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from openai import AzureOpenAI


app = Flask(__name__)
app.secret_key = '8228.12349876999'  # Clave segura para sesiones

# 🔹 Conexión a MongoDB
mongo_uri = "mongodb+srv://david01mc:1234TFM.@tfm-cluster.lrhnd.mongodb.net/admin"
client = MongoClient(mongo_uri)

# Base de datos y colecciones correctas
db_users = client["chat_logs_db"]  # BD para logins
users_collection = db_users["users"]

db_news = client["TFM"]  # BD para noticias
news_collection = db_news["diariodecadiz"]  # Colección correcta

# 🔹 Configuración de Azure OpenAI
openai_client = AzureOpenAI(
    api_key="BsfBFXlvpnsmcW2w2qn1Tyust6sN9PTVlW6mPhPQ3275pxYnQu1eJQQJ99BAACYeBjFXJ3w3AAABACOG8GBR",
    api_version="2024-06-01",
    azure_endpoint="https://TFM-OpenAI.openai.azure.com/"
)

# **🔹 Ruta de Login / Registro**
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form['action']
        username = request.form['username']
        password = request.form['password']

        if action == 'register':
            existing_user = users_collection.find_one({'username': username})
            if existing_user:
                flash('El nombre de usuario ya está registrado. Intente con otro.')
                return redirect(url_for('login'))

            hashed_password = generate_password_hash(password)
            users_collection.insert_one({'username': username, 'password': hashed_password})
            flash('Usuario registrado con éxito.')
            return redirect(url_for('login'))

        elif action == 'login':
            user = users_collection.find_one({'username': username})
            if user and check_password_hash(user['password'], password):
                session['user'] = username  # Guardamos el usuario en sesión
                return redirect(url_for('chat', username=username))
            else:
                flash('Usuario o contraseña incorrectos.')

    return render_template('login.html')

# **🔹 Ruta del chat**
@app.route('/chat/<username>')
def chat(username):
    if 'user' not in session or session['user'] != username:
        return redirect(url_for('login'))  # Evita acceso sin login
    return render_template('chat.html', username=username)

# **🔹 API para devolver las 4 noticias más relevantes**
@app.route('/search_news', methods=['POST'])
def search_news():
    if 'user' not in session:
        return jsonify({"error": "No autorizado"}), 401  # Evita acceso sin login

    data = request.get_json()
    user_message = data.get('message', '')

    # 🔹 Generar embedding de la consulta
    try:
        response = openai_client.embeddings.create(
            input=user_message,
            model="text-embedding-ada-002"
        )
        embedding_list = response.data[0].embedding
    except Exception as e:
        print(f"⚠️ Error generando embedding: {e}")
        return jsonify({'response': "Hubo un error generando la consulta, intenta de nuevo."})

    # 🔹 Buscar las **4 noticias más relevantes** en MongoDB Atlas
    results = news_collection.aggregate([
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": embedding_list,
                "numCandidates": 100,
                "limit": 5
            }
        }
    ])

    news_results = list(results)

    # 🔹 DEBUG: Ver qué devuelve la consulta
    print(f"🔍 Consulta: {user_message}")
    print(f"📊 Resultados obtenidos: {news_results[0].get("description", "Sin descripción")}")

    if news_results:
        formatted_results = []
        for i, news in enumerate(news_results):
            formatted_results.append({
                "id": str(news["_id"]),
                "rank": i + 1,
                "titulo": news.get("description", "Sin descripción"),
                "url": news.get("url_noticia", "No disponible")
            })

        return jsonify({"results": formatted_results})
    
    else:
        return jsonify({"response": "Lo siento, no encontré información relevante sobre ese tema."})

# **🔹 API para elegir una noticia y preguntar sobre ella**
@app.route('/ask_news', methods=['POST'])
def ask_news():
    if 'user' not in session:
        return jsonify({"error": "No autorizado"}), 401  # Evita acceso sin login

    data = request.get_json()
    news_id = data.get('news_id', '')
    user_question = data.get('question', '')

    # Buscar la noticia en la base de datos
    selected_news = news_collection.find_one({"_id": news_id})

    if not selected_news:
        return jsonify({"response": "No se encontró la noticia seleccionada."})

    # **Construir contexto de la noticia**
    news_data = {
        "URL de la noticia": selected_news.get("url_noticia", "No disponible"),
        "Fuente": selected_news.get("origen", "No disponible"),
        "Imagen": selected_news.get("image_url", "No disponible"),
        "Autor": selected_news.get("author", "No disponible"),
        "Fecha de publicación": selected_news.get("date_published", "No disponible"),
        "Descripción": selected_news.get("description", "No disponible"),
        "Cuerpo del artículo": selected_news.get("article_body", "No disponible"),
        "Comentarios": selected_news.get("comentarios", [])
    }

    # **Truncar `article_body` y comentarios**
    if len(news_data["Cuerpo del artículo"]) > 2000:
        news_data["Cuerpo del artículo"] = news_data["Cuerpo del artículo"][:2000] + "..."

    comentarios = news_data["Comentarios"]
    comentarios_truncados = [comentario[:500] + "..." if len(comentario) > 500 else comentario for comentario in comentarios[:3]]
    news_data["Comentarios"] = "\n- ".join(comentarios_truncados) if comentarios_truncados else "Sin comentarios disponibles"

    # **Generar respuesta con GPT**
    news_context = f"""
    URL: {news_data['URL de la noticia']}
    Fuente: {news_data['Fuente']}
    Imagen: {news_data['Imagen']}
    Autor: {news_data['Autor']}
    Fecha de publicación: {news_data['Fecha de publicación']}
    
    Descripción: {news_data['Descripción']}
    
    Cuerpo del artículo: {news_data['Cuerpo del artículo']}
    
    Comentarios:
    - {news_data['Comentarios']}
    """

    try:
        chat_response = openai_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Responde con base en la siguiente noticia:"},
                {"role": "user", "content": f"{news_context}\n\nPregunta: {user_question}"}
            ],
            model="gpt-35-turbo",
        )

        bot_response = chat_response.choices[0].message.content
    except Exception as e:
        print(f"⚠️ Error en la consulta con GPT: {e}")
        bot_response = "Hubo un error al procesar la respuesta, intenta de nuevo."

    return jsonify({'response': bot_response})

# **🔹 Logout**
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
