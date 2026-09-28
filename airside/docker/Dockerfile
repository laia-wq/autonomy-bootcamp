# Airside engine image: ROS 2 Humble + MAVROS + py_trees.
#
# Deliberately simpler than the monorepo image: no colcon workspace, no
# rosbridge/rosapi. The repo is copied to /bootcamp and put on PYTHONPATH,
# and the launch file is run by absolute path.
#
# Build context is the repo root (see integration/compose.yaml):
#   docker build -f airside/docker/Dockerfile .

FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# Humble's live repository is missing MAVROS binaries (upstream issue #2293).
# Use the last complete release from the signed ROS snapshot; keep the rest
# of ROS on the live repository. Pin the messages and library to match.
RUN gpg --batch --keyserver hkp://keyserver.ubuntu.com:80 \
      --recv-keys 4B63CF8FDE49746E98FA01DDAD19BAB3CBF125EA \
    && gpg --batch --export 4B63CF8FDE49746E98FA01DDAD19BAB3CBF125EA \
      > /usr/share/keyrings/ros-snapshots.gpg \
    && printf '%s\n' 'deb [signed-by=/usr/share/keyrings/ros-snapshots.gpg] http://snapshots.ros.org/humble/2026-08-07/ubuntu jammy main' \
    > /etc/apt/sources.list.d/mavros-snapshot.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    geographiclib-tools \
    python3-pip \
    'ros-humble-mavros=2.14.0-*' \
    'ros-humble-mavros-extras=2.14.0-*' \
    'ros-humble-mavros-msgs=2.14.0-*' \
    'ros-humble-libmavconn=2.14.0-*' \
    ros-humble-py-trees \
    ros-humble-py-trees-ros \
  && rm -rf /var/lib/apt/lists/*

# MAVROS needs the GeographicLib datasets for global-frame conversions.
RUN /opt/ros/humble/lib/mavros/install_geographiclib_datasets.sh

RUN pip install --no-cache-dir numpy pyyaml

COPY . /bootcamp

# Repo root: cross-project imports (camera.src.sim, utils.src.waypoint_utils).
# airside/src: the engine package itself (engine.ros.mission, ...).
ENV PYTHONPATH=/bootcamp:/bootcamp/airside/src

COPY airside/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "/bootcamp/airside/src/engine/launch/perception.launch.py"]
