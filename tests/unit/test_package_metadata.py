from incident_agent import __version__


def test_package_version_is_exposed() -> None:
    assert __version__ == "0.1.0"
