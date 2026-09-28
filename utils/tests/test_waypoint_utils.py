"""
TODO(bootcamper): write the tests for ``src/waypoint_utils.py`` in here.

The example below covers files that parse fine: with and without ``home``,
and files with comments and blank lines in them. The rest is yours:

- Bad data: a file whose top level isn't a mapping, waypoints missing
  ``lat``, ``lon``, or ``alt``, values that aren't numbers, YAML that
  doesn't parse, and a file that isn't there.
- Out of range: latitudes past +/-90 and longitudes past +/-180 get
  rejected.
- Nothing to work with: an empty file, an empty ``waypoints`` list, and
  ``sort_clockwise_sweep`` given a list of 0 or 1 waypoints.
- ``east_north_coordinate_offset_m``: offsets you worked out yourself,
  compared with ``pytest.approx``. Never use ``==`` on meters.
- Ordering: with no ``home``, ``sort_clockwise_sweep`` goes clockwise
  starting from north.
- With a ``home``: the order starts in home's direction instead, and goes
  back to starting at north if home is right on top of the centroid.
- Two waypoints in the same direction: the closer one comes first.
- Parsing gives you frozen ``Coordinate`` objects that can't be changed.

Graded by ``warg run utils grade-tests``: pass on the real code, 90% branch
coverage, and fail on every broken copy in ``grader/mutants/``.
"""

from dataclasses import FrozenInstanceError

import pytest

from src.types import Coordinate
from src.waypoint_utils import (
    east_north_coordinate_offset_m,
    parse_waypoints_file,
    sort_clockwise_sweep,
)

# The helper and the test below are given to you.


def write_to_tmp_waypoints_file(tmp_path, text):
    """Write ``text`` to a YAML file and hand back its path.

    ``tmp_path`` is a pytest fixture: a fresh empty directory per test.
    """
    path = tmp_path / "waypoints.yaml"
    path.write_text(text)
    return path


# One test, three files. ``parametrize`` runs the test body once per
# ``(text, expected)`` pair, and ``ids`` names each run so a failure tells you
# which file broke.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            """
            home: {lat: 1, lon: 2, alt: 3}
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
        (
            """
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
              - {lat: 7, lon: 8, alt: 9}
            """,
            (None, [Coordinate(4, 5, 6), Coordinate(7, 8, 9)]),
        ),
        (
            """
            # a lap

            home: {lat: 1, lon: 2, alt: 3}

            waypoints:
              # first leg
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
    ],
    ids=["home-and-waypoints", "no-home", "comments-and-blank-lines"],
)
def test_parse_waypoints_file_success(tmp_path, text, expected):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == expected


@pytest.mark.parametrize("text", ["", "# empty", "{}", "waypoints: []", "home: null"])
def test_empty_waypoint_inputs(tmp_path, text):
    assert parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text)) == (
        None,
        [],
    )


@pytest.mark.parametrize("text", ["[]", "hello", "42"])
def test_top_level_must_be_mapping(tmp_path, text):
    with pytest.raises(ValueError, match="expected a mapping"):
        parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text))


@pytest.mark.parametrize("entry", ["{lat: 1}", "hello", "42"])
def test_waypoints_must_be_list(tmp_path, entry):
    with pytest.raises(ValueError, match="must be a list"):
        parse_waypoints_file(
            write_to_tmp_waypoints_file(tmp_path, "waypoints: " + entry)
        )


@pytest.mark.parametrize("location", ["home", "waypoint"])
@pytest.mark.parametrize(
    "entry, message",
    [
        ("hello", "must be a mapping"),
        ("{lon: 2, alt: 3}", "missing key"),
        ("{lat: 1, alt: 3}", "missing key"),
        ("{lat: 1, lon: 2}", "missing key"),
        ("{lat: nope, lon: 2, alt: 3}", "non-numeric"),
        ("{lat: 1, lon: nope, alt: 3}", "non-numeric"),
        ("{lat: 1, lon: 2, alt: null}", "non-numeric"),
        ("{lat: 90.01, lon: 2, alt: 3}", "out of range"),
        ("{lat: -90.01, lon: 2, alt: 3}", "out of range"),
        ("{lat: 1, lon: 180.01, alt: 3}", "out of range"),
        ("{lat: 1, lon: -180.01, alt: 3}", "out of range"),
    ],
)
def test_invalid_coordinates(tmp_path, location, entry, message):
    text = f"home: {entry}" if location == "home" else f"waypoints: [{entry}]"
    with pytest.raises(ValueError, match=message):
        parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text))


def test_invalid_yaml(tmp_path):
    with pytest.raises(ValueError, match="invalid YAML"):
        parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, "waypoints: ["))


def test_missing_file(tmp_path):
    with pytest.raises(OSError):
        parse_waypoints_file(tmp_path / "missing.yaml")


@pytest.mark.parametrize("lat, lon", [(90, 180), (-90, -180)])
def test_coordinate_boundaries_and_numeric_strings(tmp_path, lat, lon):
    text = f'waypoints: [{{lat: "{lat}", lon: "{lon}", alt: "-3.5"}}]'
    home, points = parse_waypoints_file(write_to_tmp_waypoints_file(tmp_path, text))
    assert home is None
    assert points == [Coordinate(lat, lon, -3.5)]
    assert isinstance(points[0].lat, float)


@pytest.mark.parametrize("field", ["lat", "lon", "alt"])
def test_parsed_coordinates_are_frozen(tmp_path, field):
    home, points = parse_waypoints_file(
        write_to_tmp_waypoints_file(
            tmp_path,
            "home: {lat: 1, lon: 2, alt: 3}\nwaypoints: [{lat: 4, lon: 5, alt: 6}]",
        )
    )
    for coordinate in (home, points[0]):
        with pytest.raises(FrozenInstanceError):
            setattr(coordinate, field, 99)


# One degree of arc on the specified mean-Earth sphere is 111195.0802 m.
# East/west distance at latitude 60 is half the equatorial distance.
@pytest.mark.parametrize(
    "coordinates, expected",
    [
        ((0, 0, 0, 0), (0, 0)),
        ((0, 0, 0, 1), (111195.0802, 0)),
        ((0, 0, 1, 0), (0, 111195.0802)),
        ((60, 10, 60, 11), (55597.5401, 0)),
        ((60, 11, 60, 10), (-55597.5401, 0)),
        ((1, 0, 0, 0), (0, -111195.0802)),
        ((0, 0, 60, 1), (96297.7643, 6671704.8140)),
    ],
)
def test_coordinate_offsets(coordinates, expected):
    assert east_north_coordinate_offset_m(*coordinates) == pytest.approx(
        expected, abs=0.01
    )


@pytest.mark.parametrize("points", [[], [Coordinate(1, 2, 3)]])
def test_short_sweeps_return_a_copy(points):
    result = sort_clockwise_sweep(points)
    assert result == points
    assert result is not points


@pytest.fixture
def compass():
    return [
        Coordinate(1, 0, 10),
        Coordinate(0, 1, 20),
        Coordinate(-1, 0, 30),
        Coordinate(0, -1, 40),
    ]


def test_clockwise_from_north_without_mutating_input(compass):
    north, east, south, west = compass
    points = [south, west, east, north]
    before = points.copy()
    assert sort_clockwise_sweep(points) == compass
    assert points == before


@pytest.mark.parametrize(
    "home, rotation",
    [
        (Coordinate(0, 2, 0), 1),
        (Coordinate(-2, 0, 0), 2),
        (Coordinate(0, -2, 0), 3),
        (Coordinate(0, 0, 99), 0),
    ],
)
def test_home_controls_start_direction(compass, home, rotation):
    assert sort_clockwise_sweep(list(reversed(compass)), home) == (
        compass[rotation:] + compass[:rotation]
    )


def test_same_bearing_is_sorted_near_to_far():
    near = Coordinate(1, 0, 10)
    far = Coordinate(2, 0, 20)
    south = Coordinate(-3, 0, 30)  # centroid remains (0, 0)
    assert sort_clockwise_sweep([far, south, near]) == [near, far, south]


def test_sweep_is_relative_to_centroid_not_coordinate_origin():
    north = Coordinate(44, -80, 1)
    east = Coordinate(43, -79, 2)
    south = Coordinate(42, -80, 3)
    west = Coordinate(43, -81, 4)
    assert sort_clockwise_sweep([west, south, east, north]) == [
        north,
        east,
        south,
        west,
    ]
