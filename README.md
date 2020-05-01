# CommCare Data Export Tool Management Interface

Management Interface for the CommCare Data Export Tool.

Some additional context on this project can be [found here](https://docs.google.com/document/d/1r8ZQAjCGbxX8pXWtIq0ODJOpqqI27YqPDN4vuR_CLGw/edit) (Dimagi Internal).

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

Celery is used to run background tasks. To run it you can use:

```bash
celery -A commcare_det_web worker -l info
```

Or to also include periodic tasks:

```bash
celery -A commcare_det_web worker -l info -B
```


## Running Tests

To run tests:

```bash
./manage.py test
```
