import os
from flask import Flask, request, redirect, session, url_for, render_template, jsonify, flash
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from mistralai import Mistral  
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

api_key = os.environ["MISTRAL_API_KEY"]
spotify_client_id = os.environ["SPOTIFY_CLIENT_ID"]
spotify_client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
model = "mistral-large-latest"

client = Mistral(api_key=api_key)  # Initialize your MistralAI client

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_subscribed = db.Column(db.Boolean, default=False)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('user_login'))
        return f(*args, **kwargs)
    return decorated_function

# Spotify OAuth setup
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_NAME'] = 'spotify_session'

scope = 'user-library-read user-top-read playlist-modify-private playlist-modify-public user-read-recently-played'

sp_oauth = SpotifyOAuth(
    client_id=spotify_client_id,
    client_secret=spotify_client_secret,
    redirect_uri="http://192.168.0.92:8888/callback",  # Update with your local IP address
    scope=scope
)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('user_login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    if 'user_id' in session:
        return redirect(url_for('me'))  

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['is_subscribed'] = user.is_subscribed
            return redirect(url_for('me'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('user_login'))

@app.route('/subscribe')
@login_required
def subscribe():
    user = User.query.get(session['user_id'])
    user.is_subscribed = True
    db.session.commit()
    return redirect(url_for('me'))

@app.route('/')
def login():
    return redirect(sp_oauth.get_authorize_url())

@app.route('/callback')
def callback():
    token_info = sp_oauth.get_access_token(request.args['code'])
    session['token_info'] = token_info
    print("Token info stored in session:", token_info)  
    return redirect(url_for('me'))

@app.route('/me')
@login_required
def me():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info  

    sp = Spotify(auth=token_info['access_token'])

    # Get user's playlists
    playlists = sp.current_user_playlists()['items']
    
    return render_template('playlists.html', playlists=playlists)

@app.route('/generate_playlist', methods=['POST'])
@login_required
def generate_playlist():
    try:
        user_input = request.json.get("mood")
        favorite_genre = request.json.get("favorite_genre")
        include_explicit = request.json.get("include_explicit", True)
        
        # Get the song suggestions from llm
        llm_response = client.chat.complete(
            model=model,
            messages=[{'role': 'user', 
                       'content': f'Suggest me AT LEAST 25 UNIQUE SONGS for the mood which is "{user_input}" with a STRICT focus on the "{favorite_genre}" genre. Without any Comments or Lyrics. Make a list'}]
        )

        song_list_raw = llm_response.choices[0].message.content
        song_list = [line.split('. ', 1)[1] for line in song_list_raw.split('\n') if '. ' in line]

        token_info = session.get('token_info', None)
        if not token_info:
            return redirect('/')
        
        sp = Spotify(auth=token_info['access_token'])
        
        user = sp.current_user()
        playlist_name = f"{user_input.capitalize()} Playlist"
        new_playlist = sp.user_playlist_create(user['id'], playlist_name, public=False)
        
        playlist_tracks = set()  # Use a set to ensure unique tracks
        min_songs = 25  # Ensure at least 25 songs are added

        for song in song_list:
            results = sp.search(q=song, type='track', limit=10)  # Increase the search limit
            if results['tracks']['items']:
                for track in results['tracks']['items']:
                    if not include_explicit and track['explicit']:
                        continue
                    track_id = track['id']
                    if track_id not in playlist_tracks:
                        playlist_tracks.add(track_id)
                        if len(playlist_tracks) >= min_songs:
                            break
            if len(playlist_tracks) >= min_songs:
                break
        
        # If fewer than 25 songs are found, continue searching
        if len(playlist_tracks) < min_songs:
            for song in song_list:
                if len(playlist_tracks) >= min_songs:
                    break
                results = sp.search(q=song, type='track', limit=10)
                if results['tracks']['items']:
                    for track in results['tracks']['items']:
                        if not include_explicit and track['explicit']:
                            continue
                        track_id = track['id']
                        if track_id not in playlist_tracks:
                            playlist_tracks.add(track_id)
                            if len(playlist_tracks) >= min_songs:
                                break
        
        sp.user_playlist_add_tracks(user['id'], new_playlist['id'], list(playlist_tracks))
        
        playlist_url = new_playlist['external_urls']['spotify']
        return jsonify({"message": "Playlist created successfully", "playlist_url": playlist_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/recommendations', methods=['GET'])
@login_required
def recommendations():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info  

    sp = Spotify(auth=token_info['access_token'])

    # Get personalized recommendations based on user's top tracks
    top_tracks = sp.current_user_top_tracks(limit=20)['items']
    top_artists = [track['artists'][0]['id'] for track in top_tracks]
    recommendations = sp.recommendations(seed_artists=top_artists, limit=20)['tracks']

    return render_template('recommendations.html', recommendations=recommendations)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8888, debug=True)
