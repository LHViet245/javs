"""NFO XML generator for media server compatibility.

Replaces Javinizer's Get-JVNfo.ps1 (357 lines of string concatenation)
with proper lxml XML generation.
"""

from __future__ import annotations

from lxml import etree

from javs.config.models import NfoConfig
from javs.models.movie import MovieData
from javs.utils.logging import get_logger

logger = get_logger(__name__)


class NfoGenerator:
    """Generate NFO XML files compatible with Kodi/Emby/Jellyfin.

    Uses lxml for proper XML construction instead of string interpolation,
    ensuring valid XML output every time.
    """

    def __init__(self, config: NfoConfig | None = None) -> None:
        self.config = config or NfoConfig()

    def generate(
        self,
        data: MovieData,
        original_path: str | None = None,
    ) -> str:
        """Generate NFO XML content from MovieData.

        Args:
            data: Movie metadata to serialize.
            original_path: Optional original file path to embed.

        Returns:
            UTF-8 XML string.
        """
        root = etree.Element("movie")

        # Core fields
        self._add_element(root, "title", data.display_name or data.title)
        self._add_element(root, "originaltitle", data.alternate_title)
        self._add_element(root, "id", data.id)
        self._add_element(
            root, "premiered", data.release_date.isoformat() if data.release_date else None
        )
        self._add_element(root, "year", str(data.release_year) if data.release_year else None)
        self._add_element(root, "director", data.director)
        self._add_element(root, "studio", data.maker)

        # Rating
        if data.rating:
            self._add_element(root, "rating", str(data.rating.rating))
            self._add_element(root, "votes", str(data.rating.votes))

        # Description
        self._add_element(root, "plot", data.description)
        self._add_element(root, "runtime", str(data.runtime) if data.runtime else None)
        self._add_element(root, "trailer", data.trailer_url)
        self._add_element(root, "mpaa", "XXX")
        self._add_element(root, "tagline", data.tagline)
        self._add_element(root, "set", data.series)
        self._add_element(root, "thumb", data.cover_url)

        # Original path
        if self.config.original_path and original_path:
            self._add_element(root, "originalpath", original_path)

        # Tags
        for tag in data.tags:
            self._add_element(root, "tag", self._escape(tag))

        # Credits
        for credit in data.credits:
            self._add_element(root, "credits", self._escape(credit))

        # Genres
        for genre in data.genres:
            self._add_element(root, "genre", self._escape(genre))

        # Actors/Actresses
        self._add_actors(root, data)

        # Media info
        if self.config.media_info and data.media_info:
            self._add_media_info(root, data)

        # Serialize
        xml_bytes = etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )
        return xml_bytes.decode("utf-8")

    def _add_actors(self, root: etree._Element, data: MovieData) -> None:
        """Add actor elements for each actress."""
        for actress in data.actresses:
            actors_to_add = self._resolve_actor_names(actress)

            for actor_info in actors_to_add:
                actor_el = etree.SubElement(root, "actor")
                self._add_element(actor_el, "name", actor_info["name"])
                self._add_element(actor_el, "altname", actor_info.get("altname"))
                self._add_element(actor_el, "thumb", actress.thumb_url)

                # Role handling
                if self.config.alt_name_role and actor_info.get("altname"):
                    self._add_element(actor_el, "role", actor_info["altname"])
                elif self.config.add_generic_role:
                    self._add_element(actor_el, "role", "Actress")

    def _resolve_actor_names(self, actress) -> list[dict[str, str | None]]:
        """Resolve actor names based on language and order preferences."""
        actors: list[dict[str, str | None]] = []

        if self.config.actress_language_ja:
            # Prefer Japanese name
            if actress.japanese_name:
                primary_name = actress.japanese_name
                alt_name = self._english_name(actress)
            else:
                primary_name = self._english_name(actress)
                alt_name = None
        else:
            # Prefer English name
            eng_name = self._english_name(actress)
            if eng_name:
                primary_name = eng_name
                alt_name = actress.japanese_name
            else:
                primary_name = actress.japanese_name or "Unknown"
                alt_name = None

        if primary_name:
            actors.append({"name": primary_name, "altname": alt_name})

        # Add aliases if configured
        if self.config.add_aliases:
            if self.config.actress_language_ja:
                for alias in actress.japanese_aliases:
                    actors.append({"name": alias.japanese_name, "altname": alt_name})
            else:
                for alias in actress.english_aliases:
                    name = self._format_english_name(alias.first_name, alias.last_name)
                    actors.append({"name": name, "altname": alt_name})

        return actors

    def _english_name(self, actress) -> str | None:
        """Build English name string from first/last name."""
        return self._format_english_name(actress.first_name, actress.last_name)

    def _format_english_name(self, first_name: str | None, last_name: str | None) -> str | None:
        """Format English name based on name order config."""
        if not first_name and not last_name:
            return None

        if self.config.first_name_order:
            parts = [first_name, last_name]
        else:
            parts = [last_name, first_name]

        return " ".join(p for p in parts if p).strip() or None

    @staticmethod
    def _add_element(parent: etree._Element, tag: str, text: str | None) -> etree._Element | None:
        """Add a child element with text content if text is non-empty."""
        el = etree.SubElement(parent, tag)
        el.text = text or ""
        return el

    @staticmethod
    def _escape(text: str) -> str:
        """Escape special XML characters in text content."""
        # lxml handles & and < automatically, but we normalize slashes
        return text.replace("/", "-") if text else ""
