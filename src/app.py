import os
from flask import Flask, request, redirect, session, url_for, render_template, jsonify
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from ollama import chat, ChatResponse

app = Flask(__name__)

# Spotify OAuth setup
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_NAME'] = 'spotify_session'

scope = 'user-library-read user-top-read playlist-modify-private playlist-modify-public'

sp_oauth = SpotifyOAuth(
    client_id="f4641d2910514ecd8ea3512dd56acf19",
    client_secret="fc6386b44b2a4ab2bbd77fd0314b5b97",
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

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    user_input = request.json.get("mood")
    favorite_genre = request.json.get("favorite_genre")
    
    # Get the song suggestions from Ollama
    ollama_response = chat(model='mistral', messages=[
        {'role': 'user', 'content': f'Suggest me at least 25 songs for the mood "{user_input}" with a STRICT focus on the {favorite_genre} genre.'},
    ])
    
    if 'message' in ollama_response and ollama_response['message']:
        spotify_query = ollama_response['message']['content']
    else:
        return {'error': 'Ollama response format is incorrect or no choices found.'}, 400
    
    song_list = [line.strip().split('"')[1] for line in spotify_query.split('\n') if '"' in line]
    
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
        # Search for each song in Spotify
        results = sp.search(q=song, type='track', limit=1)
        
        if results['tracks']['items']:
            track_id = results['tracks']['items'][0]['id']
            playlist_tracks.append(track_id)
        else:
            print(f"Track not found for: {song}")
    
    # If no tracks were found, return an error
    if not playlist_tracks:
        return {'error': 'No tracks found for the mood.'}, 404
    
    # Add the found tracks to the new playlist
    sp.playlist_add_items(new_playlist['id'], playlist_tracks)
    
    return jsonify({'message': 'Playlist created and tracks added!', 'playlist_url': new_playlist['external_urls']['spotify']})


if __name__ == '__main__':
    app.run(port=8888)
