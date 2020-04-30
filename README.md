# CommCare Data Export Tool Management Interface

Management Interface for the CommCare Data Export Tool

## Installation

Setup a virtualenv and install requirements:

```bash
mkvirtualenv --no-site-packages commcare_det_web -p python3.8
pip install -r requirements.txt
```

## Running server

```bash
./manage.py runserver
```

## Building front-end

To build JavaScript and CSS files, first install npm packages:

```bash
npm install
```

Then to build (and watch for changes locally) just run:

```bash
npm run dev-watch
```

## Running Celery

Celery can be used to run background tasks. To run it you can use:

```bash
celery -A commcare_det_web worker -l info
```


## Running Tests

To run tests simply run:

```bash
./manage.py test
```
