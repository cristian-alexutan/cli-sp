import dotenv
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

def create_client():
	scope = 'user-read-currently-playing user-modify-playback-state user-read-playback-state playlist-read-private user-library-read'

	dotenv.load_dotenv()
	client_id = os.getenv('CLIENT_ID')
	client_secret = os.getenv('CLIENT_SECRET')
	redirect_url = os.getenv('REDIRECT_URL')

	oauth = SpotifyOAuth(
		client_id=client_id,
		client_secret=client_secret,
		redirect_uri=redirect_url,
		scope=scope
	)

	return spotipy.Spotify(auth_manager = oauth)

if __name__ == '__main__':
	sp = create_client()