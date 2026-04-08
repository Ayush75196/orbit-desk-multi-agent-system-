from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    google_cloud_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    vertex_model: str = os.getenv("VERTEX_MODEL", "gemini-2.5-pro")
    firestore_database: str = os.getenv("FIRESTORE_DATABASE", "(default)")


settings = Settings()
