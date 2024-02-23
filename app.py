from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
import os
import json
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'mp4'}

login_manager = LoginManager()
login_manager.init_app(app)

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password
        self.uploads = []
        self.subscribers = 0
        self.subscriptions = set()

    def subscribe(self, user):
        self.subscriptions.add(user.id)

    def unsubscribe(self, user):
        if user.id in self.subscriptions:
            self.subscriptions.remove(user.id)

    def is_subscribed(self, user):
        return user.id in self.subscriptions
    
    def view_video(self, video_title):
        video = next((upload for upload in self.uploads if upload['title'] == video_title), None)
        if video:
            video['views'] += 1


def load_users():
    try:
        with open('users.json', 'r') as file:
            users_data = json.load(file)
        users = []
        for user_data in users_data.get('users', []):
            user_id = len(users) + 1
            user = User(user_id, user_data.get('username', ''), user_data.get('password', ''))
            user.uploads = user_data.get('uploads', [])
            user.subscribers = user_data.get('subscribers', 0)
            user.subscriptions = set(user_data.get('subscriptions', []))
            users.append(user)
        return users
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return []
    
def get_subscribers_count(username):
    users = load_users()
    user = next((u for u in users if u.username == username), None)
    if user:
        return user.subscribers
    else:
        return 0

def save_users(users):
    users_data = {'users': []}
    for user in users:
        user_data = {
            'user_id': user.id,
            'username': user.username,
            'password': user.password,
            'uploads': user.uploads,
            'subscribers': user.subscribers,
            'subscriptions': [sub_user for sub_user in user.subscriptions]
        }
        users_data['users'].append(user_data)
    with open('users.json', 'w') as file:
        json.dump(users_data, file, indent=4, default=lambda x: x.__dict__)

def get_all_videos():
    users = load_users()
    all_videos = []
    for user in users:
        uploads = user.uploads
        for upload in uploads:
            filename = upload['filename']
            title = upload['title']
            description = upload['description']
            video_info = {'filename': filename, 'title': title, 'description': description}
            all_videos.append(video_info)
    return all_videos

users = load_users()

@login_manager.user_loader
def load_user(user_id):
    return next((user for user in users if user.id == int(user_id)), None)

@login_manager.unauthorized_handler
def unauthorized():
    flash('You need to login first.', 'error')
    next_url = request.url if request.method == 'GET' else None
    return redirect(url_for('login', next=next_url))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def obtener_video():
    if current_user.is_authenticated:
        user_id = current_user.id
        with open('users.json', 'r') as file:
            users_data = json.load(file)
        usuario_actual = next((usuario for usuario in users_data['users'] if usuario['user_id'] == user_id), None)
        if usuario_actual:
            subidas = usuario_actual['uploads']
            if subidas:
                ultimo_video = subidas[-1]
                url = url_for('uploaded_file', filename=ultimo_video['filename'])
                return {'titulo': ultimo_video['title'], 'descripcion': ultimo_video['description'], 'url': url}
    return None

# Cargar los datos de los usuarios desde users.json
def cargar_usuarios():
    with open('users.json', 'r') as file:
        return json.load(file)['users']

# Función para buscar videos en los datos de los usuarios
def buscar_videos(query):
    resultados = []
    usuarios = cargar_usuarios()
    for usuario in usuarios:
        for carga in usuario.get('uploads', []):
            if query.lower() in carga['title'].lower():
                resultados.append(carga)
    return resultados

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    return redirect(url_for('show_videos'))

@app.route('/base1')
@login_required
def base1():
    if current_user:
        user_uploads = current_user.uploads
        return render_template('base1.html', upload=user_uploads, number_of_subscribers=current_user.subscribers, secure_filename=secure_filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        users = load_users()
        user = next((u for u in users if u.username == form.username.data), None)
        if user and user.password == form.password.data:
            login_user(user)
            return redirect(url_for('show_videos'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            with open('users.json', 'r') as file:
                users_data = json.load(file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            users_data = {'users': []}

        user_id = str(len(users_data['users']) + 1)

        new_user = {
            'user_id': user_id,
            'username': form.username.data,
            'password': form.password.data,
            'uploads': [],
            'subscribers': 0,
            'subscriptions': [],  # Agregar el atributo subscriptions al crear un nuevo usuario
        }

        users_data['users'].append(new_user)

        with open('users.json', 'w') as file:
            json.dump(users_data, file, indent=4)

        # Cargar usuarios nuevamente después de registrar un nuevo usuario
        global users
        users = load_users()

        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    total_size_mb = 0
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)

        file = request.files['file']
        title = request.form.get('title', '')
        description = request.form.get('description', '')
        views = request.form.get('views', 0)

        if file.filename == '':
            return redirect(request.url)

        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            filename = secure_filename(title) + '.mp4'
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Verificar si ya existe un archivo con el mismo nombre
            if os.path.exists(file_path):
                # Generar un nuevo nombre con un sufijo numérico
                suffix = 1
                while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], f"{title}_{suffix}.mp4")):
                    suffix += 1
                filename = f"{title}_{suffix}.mp4"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            file.save(file_path)

            # Obtener el tamaño total del archivo en MB
            total_size_mb = os.path.getsize(file_path) / (1024 * 1024)

            # Crear un archivo temporal para almacenar el progreso de la subida
            progress_file_path = file_path + '.progress'
            with open(progress_file_path, 'w') as progress_file:
                progress_file.write('0')

            info_filename = file_path + '.info'
            with open(info_filename, 'w') as info_file:
                info_file.write(f'Título: {title}\n')
                # Añadir la fecha de subida al archivo de metadatos de la descripción
                current_date = datetime.datetime.now().strftime("%d/%m/%y")
                description_with_date = f'{description} [Subido:{current_date}]'
                info_file.write(f'Descripción: {description_with_date}\n')

            # Obtener el usuario actual que está subiendo el video
            current_user.uploads.append({'filename': filename, 'title': title, 'description': description, 'views': 0})

            # Actualizar la descripción del video en el usuario que lo subió en users.json
            for user in users:
                if user == current_user:
                    user.uploads[-1]['description'] = description_with_date
                    break

            # Guardar los datos actualizados de los usuarios
            save_users(users)

            return redirect(url_for('show_videos'))
        else:
            return redirect(request.url)

    # Solo se ejecuta para solicitudes GET
    return render_template('upload.html', total_size_mb=total_size_mb)

@app.route('/canales/<username>', methods=['GET', 'POST'])
@login_required
def canal(username):
    user = next((u for u in load_users() if u.username == username), None)
    if user:
        number_of_subscribers = get_subscribers_count(username)
        if user == current_user:  # Verificar si el usuario está viendo su propio canal
            return redirect('/base1')
        else:
            return render_template('canal_base.html', user=user, current_user=current_user, number_of_subscribers=number_of_subscribers, secure_filename=secure_filename)
    else:
        return redirect(url_for('show_videos'))

@app.route('/videos', methods=['GET', 'POST'])
@login_required
def show_videos():
    videos_info = get_all_videos()
    return render_template('videos.html', videos_info=videos_info)

@app.route('/watch/<video_filename>', methods=['GET', 'POST'])
@login_required
def watch_video(video_filename):
    video_title = None
    video_description = None
    video_views = None
    uploader_name = None

    # Buscar el video en los datos de los usuarios
    for user in users:
        for upload in user.uploads:
            if upload['filename'] == video_filename + '.mp4':
                video_title = upload['title']
                video_description = upload['description']
                video_views = upload.get('views', 0)  # Obtener el recuento de vistas del video
                uploader_name = user.username
                break
        if video_title:
            break

    if video_title:
        # Incrementar el contador de vistas del video
        video_views += 1

        # Actualizar las vistas del video en los datos del usuario
        for user in users:
            for upload in user.uploads:
                if upload['filename'] == video_filename + '.mp4':
                    upload['views'] = video_views
                    break

        # Guardar los datos actualizados de los usuarios
        save_users(users)

        # Construir la URL completa del video usando url_for
        video_url = url_for('uploaded_file', filename=video_filename + '.mp4')

        # Construir la URL del canal del uploader
        uploader_url = url_for('canal', username=uploader_name)

        # Renderizar la plantilla watch.html con los datos del video
        return render_template('watch.html', title=video_title, description=video_description, video_url=video_url, views=video_views, uploader_name=uploader_name, uploader_url=uploader_url)
    else:
        return redirect(url_for('show_videos'))

@app.route('/subscribe/<username>', methods=['POST'])
@login_required
def subscribe(username):
    user_to_subscribe = next((u for u in users if u.username == username), None)
    if user_to_subscribe:
        if user_to_subscribe != current_user:
            if current_user.is_subscribed(user_to_subscribe):
                flash('¡Ya estás suscrito a {}!'.format(username), 'error')
            else:
                current_user.subscribe(user_to_subscribe)
                user_to_subscribe.subscribers += 1  # Incrementa el contador de suscriptores del usuario al que te suscribes
                save_users(users)
    return redirect(url_for('canal', username=username))

@app.route('/unsubscribe/<username>', methods=['POST'])
@login_required
def unsubscribe(username):
    user_to_unsubscribe = next((u for u in users if u.username == username), None)
    if user_to_unsubscribe:
        if user_to_unsubscribe != current_user:
            current_user.unsubscribe(user_to_unsubscribe)
            user_to_unsubscribe.subscribers -= 1  # Disminuir el contador de suscriptores del usuario al que te desuscribes
            save_users(users)
    return redirect(url_for('canal', username=username))

@app.errorhandler(404)
def internal_server_error(error):
    return redirect(request.referrer or url_for('index'))

@app.route('/uploads/<filename>', methods=['GET', 'POST'])
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/buscar/')
def buscar():
    query = request.args.get('query', '')
    
    # Buscar en los títulos de los videos
    resultados_videos = buscar_videos(query)

    # Buscar en los nombres de usuario
    usuarios = cargar_usuarios()
    resultados_usuarios = [usuario for usuario in usuarios if query.lower() in usuario['username'].lower()]

    return render_template('videos.html', videos_info=resultados_videos, canales=resultados_usuarios)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port="80")