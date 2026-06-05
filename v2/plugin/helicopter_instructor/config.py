"""Configuration manager submodule for Helicopter Flight Instructor."""

import json
import logging
import os

# pyrefly: ignore [missing-import]
import xp

from helicopter_instructor.autopilot.helicopter_control import AutopilotGains

log = logging.getLogger("helicopter_instructor")


def get_gains_filepath(plugin_dir):
    """Constructs a gains filepath based on the currently loaded aircraft.

    Args:
        plugin_dir: The plugin directory path.

    Returns:
        A string absolute path to the PID gains JSON file.
    """
    autopilot_dir = os.path.join(plugin_dir, "autopilot")
    try:
        filename, _ = xp.getNthAircraftModel(0)
        if filename:
            name_base = os.path.splitext(filename)[0]
            aircraft_name = "".join(
                c if c.isalnum() or c == "_" else "_" for c in name_base
            )
            gains_filename = f"autopilot_gains_{aircraft_name}.json"
            return os.path.join(autopilot_dir, gains_filename)
    except Exception as e:
        log.error(f"Error getting aircraft filename: {e}")
    return os.path.join(autopilot_dir, "autopilot_gains.json")


def save_gains(plugin_dir, gains):
    """Saves AutopilotGains parameters to a local JSON file.

    Args:
        plugin_dir: The plugin directory path.
        gains: An AutopilotGains instance.
    """
    if not gains:
        return
    try:
        filepath = get_gains_filepath(plugin_dir)
        # Ensure the directory exists before saving
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(gains.to_dict(), f, indent=4)
        log.info(f"Saved PID gains to {os.path.basename(filepath)}.")
    except Exception as e:
        log.error(f"Error saving gains: {e}")


def load_gains(plugin_dir):
    """Loads PID parameters from a JSON file into AutopilotGains.

    Args:
        plugin_dir: The plugin directory path.

    Returns:
        AutopilotGains instance, or None if file not found/error occurred.
    """
    filepath = get_gains_filepath(plugin_dir)
    if not os.path.exists(filepath):
        generic_filepath = os.path.join(
            plugin_dir, "autopilot", "autopilot_gains.json"
        )
        if os.path.exists(generic_filepath):
            filepath = generic_filepath
        else:
            return None
    try:
        with open(filepath, "r") as f:
            data = json.load(f)

        gains = AutopilotGains.from_dict(data)
        log.info(f"Loaded PID gains from {os.path.basename(filepath)}.")
        return gains
    except Exception as e:
        log.error(f"Error loading gains: {e}")
        return None

