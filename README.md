
## TABLE OF CONTENTS

1. [Description](#description)
2. [Setup Steps](#setup-steps)


## Description

A web app where you can put you and your friend's location and get instant restaurant recommendations in between the two of you. Be able to update and save recommended restaurants and keep building your foodie profile!
## Setup Steps

**Create a Virtual Environment:**

- _Mac:_

  ```
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- _Windows:_
  ```
  python3 -m venv .venv
  .venv\Scripts\activate
  ```

**Install Dependencies:**

```
pip install opencv-python-headless
pip install pytest pytest-cov
pip install requests
pip install pymongo
pip install -r requirements.txt
```


```
export FLASK_APP=webapp/app.py 

flask run
```

fresh environment

```
rm -rf .venv
python -m venv .venv
source .venv/bin/activate  # On Mac/Linux
pip install -r requirements.txt

```


Get Eating!:** Access Gourmate [here](https://gourmate.onrender.com/)!