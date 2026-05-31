import os
import sys
import unittest
from unittest import mock

# Set up paths so we can import helicopter_instructor
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(base_dir, '..', 'plugin', 'helicopter_instructor'))
sys.path.insert(0, os.path.join(base_dir, '..', 'plugin'))

# Mock the modules before importing PI_helicopter_instructor or audio
import sys
if 'xp' not in sys.modules:
    mock_xp = mock.MagicMock()
    mock_xp.AudioRadioPilot = 2
    sys.modules['xp'] = mock_xp
else:
    mock_xp = sys.modules['xp']
    mock_xp.AudioRadioPilot = 2

if 'xp_imgui' not in sys.modules:
    sys.modules['xp_imgui'] = mock.MagicMock()
if 'imgui' not in sys.modules:
    sys.modules['imgui'] = mock.MagicMock()

# Import the audio manager
from helicopter_instructor import audio


class TestAudio(unittest.TestCase):

    def setUp(self):
        # Dynamically align with the active mock in sys.modules to prevent importlib.reload caching mismatches
        global mock_xp
        import sys
        mock_xp = sys.modules['xp']
        mock_xp.AudioRadioPilot = 2
        mock_xp.reset_mock()

        # Set up an AudioManager instance
        self.audio_manager = audio.AudioManager("/mock/plugin/dir")
        self.audio_manager.voice_volume = 0.85

    @mock.patch('os.path.exists')
    @mock.patch('os.listdir')
    @mock.patch('wave.open')
    def test_preload_sounds(self, mock_wave_open, mock_listdir, mock_exists):
        # Configure file system mocks
        mock_exists.return_value = True
        mock_listdir.return_value = ["Perfect.wav", "I have control.wav", "unrelated_file.txt"]

        # Mock the wave file reading
        mock_wav = mock.MagicMock()
        mock_wav.getnframes.return_value = 100
        mock_wav.readframes.return_value = b"\x00\x00" * 100
        mock_wav.getsampwidth.return_value = 2
        mock_wav.getframerate.return_value = 44100
        mock_wav.getnchannels.return_value = 1
        
        # wave.open context manager returns mock_wav
        mock_wave_open.return_value.__enter__.return_value = mock_wav

        # Trigger preloading
        self.audio_manager.preload_sounds()

        # Verify registration in sound_registry
        self.assertIn("Perfect.wav", self.audio_manager.sound_registry)
        self.assertIn("I have control.wav", self.audio_manager.sound_registry)
        self.assertNotIn("unrelated_file.txt", self.audio_manager.sound_registry)

        sound_info = self.audio_manager.sound_registry["Perfect.wav"]
        self.assertEqual(sound_info["data"], b"\x00\x00" * 100)
        self.assertEqual(sound_info["data_size"], 200)
        self.assertEqual(sound_info["sample_width"], 2)
        self.assertEqual(sound_info["frame_rate"], 44100)
        self.assertEqual(sound_info["num_channels"], 1)

        # Verify log output
        mock_xp.log.assert_any_call(
            "Helicopter Flight Instructor: Preloaded 2 audio assets into memory."
        )

    def test_play_sound_success(self):
        # Manually register a mock sound in sound_registry
        mock_data = b"\x01\x02\x03\x04"
        self.audio_manager.sound_registry["Perfect.wav"] = {
            "data": mock_data,
            "data_size": len(mock_data),
            "sample_width": 2,
            "frame_rate": 22050,
            "num_channels": 2,
        }

        # Mock playPCMOnBus to return a channel ID
        mock_xp.playPCMOnBus.return_value = 99

        # Play the sound
        self.audio_manager.play_sound("Perfect.wav")

        # Verify correct buffers are kept alive in AudioManager to prevent GC issues
        self.assertIn(mock_data, self.audio_manager.active_sound_buffers)

        # Verify xp.playPCMOnBus arguments
        mock_xp.playPCMOnBus.assert_called_once_with(
            mock_data,
            4,
            2,
            22050,
            2,
            0,
            2  # AudioRadioPilot
        )

        # Verify xp.setAudioVolume was called with volume setting
        mock_xp.setAudioVolume.assert_called_once_with(99, 0.85)

    def test_play_sound_not_found_logs_error_and_returns(self):
        # Act: try playing a sound that doesn't exist in registry
        self.audio_manager.play_sound("MissingSound.wav")

        # Assert: FMOD play and volume APIs must not be called
        mock_xp.playPCMOnBus.assert_not_called()
        mock_xp.setAudioVolume.assert_not_called()

        # Assert: Error log is written
        mock_xp.log.assert_called_once_with(
            "Helicopter Flight Instructor: Sound Error: Failed to play "
            "MissingSound.wav. Sound is not preloaded in memory."
        )

    def test_stop_sound(self):
        # Set active channel
        self.audio_manager.active_channel = 99
        self.audio_manager.stop_sound()

        # Verify xp.stopAudio was called and channel was cleared
        mock_xp.stopAudio.assert_called_once_with(99)
        self.assertIsNone(self.audio_manager.active_channel)

    def test_play_sound_stops_active_sound_first(self):
        # Register a mock sound
        mock_data = b"\x01\x02\x03\x04"
        self.audio_manager.sound_registry["Perfect.wav"] = {
            "data": mock_data,
            "data_size": len(mock_data),
            "sample_width": 2,
            "frame_rate": 22050,
            "num_channels": 2,
        }

        # Set currently active channel
        self.audio_manager.active_channel = 99

        # Play a new sound
        mock_xp.playPCMOnBus.return_value = 100
        self.audio_manager.play_sound("Perfect.wav")

        # Verify the previous active channel (99) was stopped first
        mock_xp.stopAudio.assert_called_once_with(99)
        # Verify the new channel is set as the active channel
        self.assertEqual(self.audio_manager.active_channel, 100)


class TestPluginAudio(unittest.TestCase):
    def setUp(self):
        # Reset and configure mocks
        global mock_xp
        mock_xp = sys.modules['xp']
        mock_xp.reset_mock()
        mock_xp.getNthAircraftModel.return_value = (None, None)
        mock_xp.getScreenBoundsGlobal.return_value = (0, 1080, 1920, 0)

        # Import/instantiate PythonInterface
        import PI_helicopter_instructor
        self.plugin = PI_helicopter_instructor.PythonInterface()
        self.plugin.audio_queue = []
        self.plugin.audio_playback_timer = 0.0
        self.plugin.last_played_sound = None

    def test_play_sound_normal_queue(self):
        # Queuing a sound when queue is empty and last played is none
        self.plugin.play_sound("Perfect.wav")
        self.assertIn("Perfect.wav", self.plugin.audio_queue)

    def test_play_sound_duplicate_check(self):
        # Set last played sound to "I have control.wav" and playback timer active (e.g. 1.0s)
        self.plugin.last_played_sound = "I have control.wav"
        self.plugin.audio_playback_timer = 1.0

        # Try to queue "I have control.wav"
        self.plugin.play_sound("I have control.wav")
        # Should be ignored and NOT added to the queue
        self.assertNotIn("I have control.wav", self.plugin.audio_queue)

    def test_play_sound_duplicate_timer_expired(self):
        # Set last played sound to "I have control.wav" but playback timer is expired/pause-only (e.g. 0.2s)
        self.plugin.last_played_sound = "I have control.wav"
        self.plugin.audio_playback_timer = 0.2

        # Try to queue "I have control.wav"
        self.plugin.play_sound("I have control.wav")
        # Should be allowed and added to the queue
        self.assertIn("I have control.wav", self.plugin.audio_queue)

    def test_play_sound_clear_queue(self):
        # Set some active state
        self.plugin.audio_queue = ["Perfect.wav", "You have all controls.wav"]
        self.plugin.audio_playback_timer = 1.5

        # Call with clear_queue = True
        self.plugin.play_sound("I have control.wav", clear_queue=True)
        # Queue should be cleared and only contain the new sound
        self.assertEqual(self.plugin.audio_queue, ["I have control.wav"])
        self.assertEqual(self.plugin.audio_playback_timer, 0.0)

    def test_play_sound_clear_queue_stops_active_sound(self):
        # Set active sound channel on the plugin's audio manager
        self.plugin.audio.active_channel = 88

        # Call play_sound with clear_queue = True
        self.plugin.play_sound("I have control.wav", clear_queue=True)

        # Verify the underlying audio manager's stop_sound was invoked (xp.stopAudio called)
        mock_xp.stopAudio.assert_called_once_with(88)
        self.assertIsNone(self.plugin.audio.active_channel)


if __name__ == '__main__':
    unittest.main()
