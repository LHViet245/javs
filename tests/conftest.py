"""Test configuration for pytest."""

import pytest


@pytest.fixture
def sample_config():
    """Create a sample JavsConfig for testing."""
    from javs.config.models import JavsConfig

    return JavsConfig()


@pytest.fixture
def sample_movie_data():
    """Create sample MovieData for testing."""
    from datetime import date

    from javs.models.movie import Actress, MovieData, Rating

    return MovieData(
        id="ABP-420",
        title="Test Movie Title",
        alternate_title="テスト映画タイトル",
        description="A test movie description",
        rating=Rating(rating=7.5, votes=100),
        release_date=date(2023, 6, 15),
        runtime=120,
        director="Test Director",
        maker="Test Studio",
        label="Test Label",
        series="Test Series",
        genres=["Drama", "Romance"],
        actresses=[
            Actress(
                last_name="Suzuki",
                first_name="Koharu",
                japanese_name="鈴木心春",
            ),
        ],
        cover_url="https://example.com/cover.jpg",
        source="test",
    )
