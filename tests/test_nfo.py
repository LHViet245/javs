"""Tests for NFO generator."""

from datetime import date

from lxml import etree

from javs.config.models import NfoConfig
from javs.core.nfo import NfoGenerator
from javs.models.movie import Actress, MovieData, Rating


class TestNfoGenerator:
    """Test NFO XML generation."""

    def setup_method(self):
        self.generator = NfoGenerator()
        self.sample_data = MovieData(
            id="ABP-420",
            title="Test Title",
            display_name="[ABP-420] Test Title",
            alternate_title="テストタイトル",
            description="Test description",
            rating=Rating(rating=7.5, votes=100),
            release_date=date(2023, 6, 15),
            runtime=120,
            director="Test Director",
            maker="Test Studio",
            series="Test Series",
            genres=["Drama", "Romance"],
            actresses=[
                Actress(
                    last_name="Suzuki",
                    first_name="Koharu",
                    japanese_name="鈴木心春",
                    thumb_url="https://example.com/thumb.jpg",
                ),
            ],
            cover_url="https://example.com/cover.jpg",
            tags=["Test Series"],
        )

    def test_generates_valid_xml(self):
        """Output should be valid XML."""
        nfo = self.generator.generate(self.sample_data)
        # Should not raise
        root = etree.fromstring(nfo.encode("utf-8"))
        assert root.tag == "movie"

    def test_contains_core_fields(self):
        """NFO should contain all core metadata fields."""
        nfo = self.generator.generate(self.sample_data)
        root = etree.fromstring(nfo.encode("utf-8"))

        assert root.find("title").text == "[ABP-420] Test Title"
        assert root.find("id").text == "ABP-420"
        assert root.find("studio").text == "Test Studio"
        assert root.find("premiered").text == "2023-06-15"
        assert root.find("year").text == "2023"
        assert root.find("plot").text == "Test description"
        assert root.find("runtime").text == "120"
        assert root.find("mpaa").text == "XXX"

    def test_contains_actors(self):
        """NFO should contain actor elements."""
        nfo = self.generator.generate(self.sample_data)
        root = etree.fromstring(nfo.encode("utf-8"))

        actors = root.findall("actor")
        assert len(actors) >= 1
        assert actors[0].find("name").text is not None

    def test_contains_genres(self):
        """NFO should contain genre elements."""
        nfo = self.generator.generate(self.sample_data)
        root = etree.fromstring(nfo.encode("utf-8"))

        genres = root.findall("genre")
        texts = [g.text for g in genres]
        assert "Drama" in texts
        assert "Romance" in texts

    def test_japanese_actress_name(self):
        """With actress_language_ja, should use Japanese names."""
        config = NfoConfig(actress_language_ja=True)
        gen = NfoGenerator(config)
        nfo = gen.generate(self.sample_data)
        root = etree.fromstring(nfo.encode("utf-8"))

        actor = root.find("actor")
        assert actor.find("name").text == "鈴木心春"

    def test_original_path_included(self):
        """Original path should be in NFO when configured."""
        config = NfoConfig(original_path=True)
        gen = NfoGenerator(config)
        nfo = gen.generate(self.sample_data, original_path="/test/path/video.mp4")
        root = etree.fromstring(nfo.encode("utf-8"))

        assert root.find("originalpath").text == "/test/path/video.mp4"

    def test_empty_data(self):
        """Should handle empty MovieData gracefully."""
        nfo = self.generator.generate(MovieData())
        root = etree.fromstring(nfo.encode("utf-8"))
        assert root.tag == "movie"
