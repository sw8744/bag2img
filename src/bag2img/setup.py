from setuptools import find_packages, setup


package_name = "bag2img"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml", "README.md"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="thislifewon",
    maintainer_email="user@example.com",
    description="Export images from ROS 2 bag and video files at a fixed interval.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "bag2img = bag2img.bag_exporter:main",
            "video2img = bag2img.video_exporter:main",
        ],
    },
)
