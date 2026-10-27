"""Read the supplied EPTS metadata and its authoritative tracking slot order."""

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class TrackingMetadata:
    """Frame rate, physical pitch size and channel-reference slot metadata."""

    fps: float
    pitch_length: float
    pitch_width: float
    speed_unit: str
    expected_frames: int
    slot_ids: tuple[str, ...]
    slot_team_ids: tuple[str, ...]
    team_names: dict[str, str]


def read_metadata(path: Path) -> TrackingMetadata:
    """Resolve channels through their refs rather than XML player-list order."""
    root = ET.parse(path).getroot()
    teams = root.findall("./Metadata/Teams/Team")
    player_teams = {
        player.attrib["id"]: player.attrib["teamId"]
        for player in root.findall("./Metadata/Players/Player")
    }
    channels = {
        item.attrib["id"]: item.attrib["playerId"]
        for item in root.findall("./Metadata/PlayerChannels/PlayerChannel")
    }
    specification = root.find("./DataFormatSpecifications/DataFormatSpecification")
    slots = specification.findall("./SplitRegister[@separator=';']/SplitRegister")
    slot_ids = tuple(
        channels[slot.find("PlayerChannelRef").attrib["playerChannelId"]]
        for slot in slots
    )
    return TrackingMetadata(
        fps=float(root.findtext("./Metadata/GlobalConfig/FrameRate")),
        pitch_length=float(
            root.findtext("./Metadata/Sessions/Session/FieldSize/Width")
        ),
        pitch_width=float(
            root.findtext("./Metadata/Sessions/Session/FieldSize/Height")
        ),
        speed_unit=root.findtext(".//Devices//Channel[@id='s']/Unit"),
        expected_frames=int(specification.attrib["endFrame"]),
        slot_ids=slot_ids,
        slot_team_ids=tuple(player_teams[identifier] for identifier in slot_ids),
        team_names={team.attrib["id"]: team.findtext("Name") for team in teams},
    )
