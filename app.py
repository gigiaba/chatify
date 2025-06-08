from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatify.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Uploads
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    reactions = db.relationship('Reaction', backref='user', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    media_filename = db.Column(db.String(300), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reactions = db.relationship('Reaction', backref='post', lazy=True)

class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_reaction'),)

# Helpers
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return dict(current_user=user)

# Routes
@app.route('/')
def home():
    posts = Post.query.order_by(Post.id.desc()).all()
    return render_template('index.html', title='Chatify', posts=posts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Login unsuccessful. Please check username and password.', 'danger')

    return render_template('login.html', title='Login - Chatify')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', title='Register - Chatify')

@app.route('/post', methods=['POST'])
def post():
    if 'user_id' not in session:
        flash('Please log in to post.', 'danger')
        return redirect(url_for('login'))

    content = request.form.get('content')
    file = request.files.get('media')

    if not content and (file is None or file.filename == ''):
        flash('Post cannot be empty.', 'danger')
        return redirect(url_for('home'))

    filename = None
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    elif file and file.filename != '':
        flash('Unsupported file type.', 'danger')
        return redirect(url_for('home'))

    new_post = Post(content=content, media_filename=filename, user_id=session['user_id'])
    db.session.add(new_post)
    db.session.commit()

    flash('Your post has been created!', 'success')
    return redirect(url_for('home'))

@app.route('/react/<int:post_id>', methods=['POST'])
def react(post_id):
    if 'user_id' not in session:
        flash('Please log in to react.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    reaction = Reaction.query.filter_by(user_id=user_id, post_id=post_id).first()

    if reaction:
        db.session.delete(reaction)
        flash('Reaction removed.', 'info')
    else:
        db.session.add(Reaction(user_id=user_id, post_id=post_id))
        flash('Post liked!', 'success')

    db.session.commit()
    return redirect(url_for('home'))

@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('home'))

    posts = Post.query.filter_by(user_id=user.id).order_by(Post.id.desc()).all()
    return render_template('profile.html', user=user, posts=posts, title=f"{username}'s Profile - Chatify")

# Initialize DB
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
