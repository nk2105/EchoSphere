import os
from flask import Flask, request, redirect, session, url_for, render_template, jsonify
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from mistralai import Mistral  # Replace with actual MistralAI client import

api_key = os.environ["MISTRAL_API_KEY"]
spotify_client_id = os.environ["SPOTIFY_CLIENT_ID"]
spotify_client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]
model = "mistral-large-latest"

client = Mistral(api_key=api_key)  # Initialize your MistralAI client

app = Flask(__name__)

# Spotify OAuth setup
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_NAME'] = 'spotify_session'

scope = 'user-library-read user-top-read playlist-modify-private playlist-modify-public user-read-recently-played'

sp_oauth = SpotifyOAuth(
    client_id=spotify_client_id,
    client_secret=spotify_client_secret,
    redirect_uri="http://localhost:8888/callback",
    scope=scope
)

@app.route('/')
def login():
    return redirect(sp_oauth.get_authorize_url())

@app.route('/callback')
def callback():
    token_info = sp_oauth.get_access_token(request.args['code'])
    session['token_info'] = token_info
    print("Token info stored in session:", token_info)  # Debugging line
    return redirect(url_for('me'))

@app.route('/me')
def me():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info  # Update the session

    sp = Spotify(auth=token_info['access_token'])

    # Get user's playlists
    playlists = sp.current_user_playlists()['items']
    
    return render_template('playlists.html', playlists=playlists)

@app.route('/top_tracks')
def top_tracks():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info  # Update session with the new token

    sp = Spotify(auth=token_info['access_token'])

    # Get the user's top tracks
    top_tracks = sp.current_user_top_tracks(limit=20)

    # Process the tracks as needed
    track_names = [track['name'] for track in top_tracks['items']]
    for name in track_names:
        print(name)

    return "Top tracks processed"

def detect_genre_of_songs(song_list):
    genre_detection_prompt = f"Detect the genre for the following songs:\n" + "\n".join(song_list)
    mistralai_response = client.chat.complete(
        model=model,
        messages=[{'role': 'user', 'content': genre_detection_prompt}]
    )
    genres = mistralai_response.choices[0].message.content.split('\n')
    return genres

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    user_input = request.json.get("mood")
    favorite_genre = request.json.get("favorite_genre")
    
    # Get the song suggestions from Ollama
    ollama_response = client.chat.complete(
        model=model,
        messages=[{'role': 'user', 
                   'content': f'Suggest me at least 25 songs for the mood "{user_input}" with a STRICT focus on the {favorite_genre} genre. Without any Comments or Lyrics. Make a list'}]
    )

    print(ollama_response.choices[0].message.content)  # Debugging line to check the full response

    song_list_raw = ollama_response.choices[0].message.content
    # Split the songs based on the number, which is prefixed with "1.", "2.", etc.
    song_list = [line.split('. ', 1)[1] for line in song_list_raw.split('\n') if '. ' in line]
    print(f"Extracted song list: {song_list}")

    # Get the user's access token and authenticate with Spotify
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    
    sp = Spotify(auth=token_info['access_token'])
    
    # Create a new playlist for the user
    user = sp.current_user()  # Get the current user details
    playlist_name = f"{user_input.capitalize()} Playlist"
    new_playlist = sp.user_playlist_create(user['id'], playlist_name, public=False)
    
    playlist_tracks = []
    
    for song in song_list:
        print(f"Searching for: {song}")
        results = sp.search(q=song, type='track', limit=1)
        if results['tracks']['items']:
            track_id = results['tracks']['items'][0]['id']
            playlist_tracks.append(track_id)
    
    # Add tracks to the new playlist
    sp.user_playlist_add_tracks(user['id'], new_playlist['id'], playlist_tracks)
    print(f"Playlist '{playlist_name}' created successfully with {len(playlist_tracks)} tracks.")
    
    # Return the playlist URL for redirection
    playlist_url = new_playlist['external_urls']['spotify']
    return jsonify({"message": "Playlist created successfully", "playlist_url": playlist_url})

if __name__ == '__main__':
    app.run(port=8888, debug=True)
