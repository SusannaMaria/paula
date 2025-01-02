from ctypes import POINTER, cast

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


def set_system_volume(level: float):
    """
    Set the system audio volume.

    :param level: Volume level as a float between 0.0 (mute) and 1.0 (max volume)
    """
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(level, None)


def get_system_volume():
    """
    Get the current system audio volume as a float between 0.0 and 1.0.

    :return: Current system volume as a float
    """
    # Get the default audio output device
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

    # Get the volume level as a scalar (0.0 to 1.0)
    current_volume = volume.GetMasterVolumeLevelScalar()
    return current_volume


# Set volume to 50%
print(get_system_volume())
set_system_volume(0.3)
