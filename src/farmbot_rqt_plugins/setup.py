from setuptools import find_packages, setup
import glob
import os

package_name = "farmbot_rqt_plugins"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages",
         ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name, ["plugin.xml"]),
        ("share/" + package_name + "/resource", ["resource/movement.ui"]),
        ("share/" + package_name + "/resource/icons", glob.glob("resource/icons/*")),
    ],
    install_requires=["setuptools", "langchain",
                      "langchain-openai", "PyYAML", "python-dotenv"],
    zip_safe=True,
    maintainer="bryanmccarthy",
    maintainer_email="BRYAN.MCCARTHY.2025@mumail.ie",
    description="TODO: Package description",
    license="TODO: License declaration",
    entry_points={
        "rqt_gui.plugin": [
            "movement_plugin = farmbot_rqt_plugins.movement_plugin:MovementPlugin",
            "farmbedtwo_plugin = farmbot_rqt_plugins.farmbedtwo_plugin:FarmbedTwoPlugin",
            "farmbot_llm_plugin = farmbot_rqt_plugins.farmbot_llm_plugin:FarmbotLLMPlugin"
        ],
    },
)
