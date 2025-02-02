**4. Create a Virtual Environment:**

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

**5. Install Dependencies:**

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