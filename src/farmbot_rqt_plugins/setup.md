# To run farmbot_llm_plugin on Ubuntu:

```
virtualenv -p python3 venv
source venv/bin/activate
touch venv/COLCON_IGNORE
```

```
  python3 -m pip install langchain langchain-openai PyYAML python-dotenv
```

```
  export PYTHONPATH=$VIRTUAL_ENV/lib/python3.12/site-packages:$PYTHONPATH
```

```
  source /opt/ros/jazzy/setup.bash
  colcon build
```
