# EchoSphere

**Spotify on Steroids**

EchoSphere is a Flask-based web application that enhances your Spotify experience by allowing you to generate custom playlists based on your mood and favorite genre. It leverages the Spotify API and MistralAI to provide personalized music recommendations.

## Features

- **User Authentication**: Register and log in to manage your playlists.
- **Custom Playlists**: Generate playlists based on your mood and favorite genre.
- **Unique Tracks**: Ensure that your playlists contain unique tracks.
- **Spotify Integration**: Seamlessly integrate with your Spotify account to create and manage playlists.
- **Explicit Content Filter**: Option to include or exclude explicit content from your playlists.

## Prerequisites
[Spotify for Developers](https://developer.spotify.com/documentation/web-api/) and [MistralAI API](https://mistral.ai/)

## Installation

1. **Clone the repository**:
   ```sh
   git clone https://github.com/yourusername/EchoSphere.git
   cd EchoSphere

2. **Create and activate a virtual environment**
    ```sh
    python3 -m venv venv
    source venv/bin/activate

3. **Install the dependencies**
    ```sh
    pip install -r requirements.txt

4. **Set up environment variables in your shell configuration file:**

    ```sh
    export OPENAI_API_KEY="yourkey"
    export MISTRAL_API_KEY="yourkey"
    export SPOTIFY_CLIENT_ID="yourid"
    export SPOTIFY_CLIENT_SECRET="yoursecret"
    export SECRET_KEY='yourkey'

    