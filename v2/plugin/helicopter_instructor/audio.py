"""Audio manager submodule for Helicopter Flight Instructor."""

from helicopter_instructor import graphics
import os
import wave

# pyrefly: ignore [missing-import]
import xp


class AudioManager(object):
    """Audio manager service that preloads WAV files and plays them."""

    def __init__(self, plugin_dir):
        """Initializes the AudioManager instance.

        Args:
            plugin_dir: The absolute path to the plugin directory.
        """
        self.assets_dir = os.path.join(plugin_dir, "assets")
        self.active_sound_buffers = []
        self.voice_volume = 1.0
        self.sound_registry = {}
        self.active_channel = None

    def preload_sounds(self):
        """Eagerly loads all WAV files in the assets directory into the sound registry to avoid synchronous disk I/O stutters."""
        if not os.path.exists(self.assets_dir):
            xp.log(f"Assets directory {self.assets_dir} not found. Preloading skipped.")
            return

        try:
            filenames = os.listdir(self.assets_dir)
        except Exception as list_err:
            xp.log(f"Failed to list assets directory. Exception: {str(list_err)}")
            return

        preloaded_count = 0
        for filename in filenames:
            if filename.lower().endswith(".wav"):
                filepath = os.path.join(self.assets_dir, filename)
                # Skip if already preloaded
                if filename in self.sound_registry:
                    continue
                try:
                    with wave.open(filepath, "rb") as wav:
                        num_frames = wav.getnframes()
                        frame_rate = wav.getframerate()
                        data = wav.readframes(num_frames)
                        duration_s = num_frames / frame_rate if frame_rate > 0 else 0.0
                        self.sound_registry[filename] = {
                            "data": data,
                            "data_size": len(data),
                            "sample_width": wav.getsampwidth(),
                            "frame_rate": frame_rate,
                            "num_channels": wav.getnchannels(),
                            "duration_s": duration_s,
                        }
                        xp.log(f"Preloaded {filename} ({duration_s:.2f} s)")
                        preloaded_count += 1
                except Exception as e:
                    xp.log(f"Failed to preload {filename}. Exception: {str(e)}")

        if preloaded_count > 0:
            xp.log(f"Preloaded {preloaded_count} audio assets into memory.")

    def play_sound(self, filename):
        """Plays a preloaded WAV file.

        Returns the duration of the sound in seconds.

        Args:
            filename: A string filename of the sound to be played.
        """
        self.stop_sound()

        sound_info = self.sound_registry.get(filename)

        if not sound_info:
            xp.log(
                f"Sound Error: Failed to play {filename}. Sound is not preloaded in memory."
            )
            return 0.0

        try:
            # Keep buffers from being garbage-collected during playback
            self.active_sound_buffers.append(sound_info["data"])
            if len(self.active_sound_buffers) > 5:
                self.active_sound_buffers.pop(0)

            audio_type = getattr(xp, "AudioRadioPilot", 2)

            # xp.playPCMOnBus parameters:
            # data, data_size, sample_width, frame_rate, num_channels,
            # loop, audioType
            channel = xp.playPCMOnBus(
                sound_info["data"],
                sound_info["data_size"],
                sound_info["sample_width"],
                sound_info["frame_rate"],
                sound_info["num_channels"],
                0,  # loop = 0 (play once)
                audio_type,
            )

            if channel:
                self.active_channel = channel
                try:
                    xp.setAudioVolume(channel, self.voice_volume)
                except Exception as volume_err:
                    xp.log(f"Failed to set audio volume. Exception: {str(volume_err)}")
        except Exception as e:
            xp.log(f"Sound Error: Failed to play {filename}. Exception: {str(e)}")

        return sound_info["duration_s"]

    def stop_sound(self):
        """Stops the currently playing audio channel if active."""
        if self.active_channel:
            try:
                xp.stopAudio(self.active_channel)
            except Exception as stop_err:
                xp.log(f"Failed to stop audio channel. Exception: {str(stop_err)}")
            self.active_channel = None
