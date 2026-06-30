from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"
    VIEWER = "VIEWER"


class ImportStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"


class Severity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EventLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class SourceType(StrEnum):
    FILE_UPLOAD = "FILE_UPLOAD"
    WFS = "WFS"
    MANUAL = "MANUAL"
    SAMPLE = "SAMPLE"


LAYER_TYPES = {
    "EGIB_PARCELS",
    "EGIB_BUILDINGS",
    "LPIS_REFERENCE_PARCELS",
    "LPIS_MKO",
    "LPIS_PZ",
    "LPIS_GSA",
    "BDOT500_FENCES",
    "GENERIC_POLYGON",
    "GENERIC_LINE",
    "GENERIC_POINT",
}

