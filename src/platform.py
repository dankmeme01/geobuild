from __future__ import annotations
from enum import Enum, auto

class Platform(Enum):
    Windows = auto()
    Android32 = auto()
    Android64 = auto()
    Mac = auto()
    Ios = auto()

    @staticmethod
    def parse(platform: str) -> Platform:
        platform = platform.lower()
        if platform == "windows" or platform == "win" or platform == "win64":
            return Platform.Windows
        elif platform == "android32":
            return Platform.Android32
        elif platform == "android64":
            return Platform.Android64
        elif platform == "macos":
            return Platform.Mac
        elif platform == "ios":
            return Platform.Ios
        else:
            raise ValueError(f"Unknown platform: {platform}")

    def platform_str(self, include_bit: bool = False) -> str:
        out = ""

        match self:
            case Platform.Windows:
                out = "windows"
            case Platform.Android32, Platform.Android64:
                out = "android"
            case Platform.Mac:
                out = "macos"
            case Platform.Ios:
                out = "ios"

        if include_bit:
            match self:
                case Platform.Android32:
                    out += "32"
                case Platform.Android64:
                    out += "64"

        return out

    def is_windows(self) -> bool:
        return self == Platform.Windows

    def is_ios(self) -> bool:
        return self == Platform.Ios

    def is_android(self) -> bool:
        return self in (Platform.Android32, Platform.Android64)

    def is_mac(self) -> bool:
        return self == Platform.Mac

    def is_desktop(self) -> bool:
        return self in (Platform.Windows, Platform.Mac)

    def is_mobile(self) -> bool:
        return not self.is_desktop()

    def is_apple(self) -> bool:
        return self in (Platform.Mac, Platform.Ios)

    def is_64bit(self) -> bool:
        return self in (Platform.Windows, Platform.Android64, Platform.Mac, Platform.Ios)

    def is_32bit(self) -> bool:
        return self == Platform.Android32
