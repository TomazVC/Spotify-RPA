import unittest
from unittest.mock import patch

import app


class PlaybackFlowTests(unittest.TestCase):
    def setUp(self):
        self.original_uri = app.PLAYLISTS[0]["uri"]
        app.PLAYLISTS[0]["uri"] = "spotify:playlist:test123"
        self.client = app.app.test_client()

    def tearDown(self):
        app.PLAYLISTS[0]["uri"] = self.original_uri

    def test_retries_start_playback_after_transient_spotify_500(self):
        calls = []

        def fake_spotify_request(method, path, token, **kwargs):
            calls.append((method, path, kwargs))
            if path == "/me/player/play" and len([c for c in calls if c[1] == path]) == 1:
                raise RuntimeError("Spotify API retornou 500: {'error': {'status': 500, 'message': 'Server error.'}}")
            return object()

        with (
            patch("app.get_access_token", return_value="fake-token"),
            patch(
                "app.get_devices",
                return_value=[
                    {
                        "id": "dev1",
                        "name": "Notebook",
                        "type": "Computer",
                        "is_active": True,
                        "is_restricted": False,
                    }
                ],
            ),
            patch("app.spotify_request", side_effect=fake_spotify_request),
            patch("app.time.sleep", return_value=None),
        ):
            response = self.client.post("/play", data={"playlist": "playlist1"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sucesso", response.get_data(as_text=True))
        play_calls = [call for call in calls if call[1] == "/me/player/play"]
        self.assertEqual(len(play_calls), 2)


if __name__ == "__main__":
    unittest.main()
