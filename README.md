# SPARA server

SPARA backend is based on FastAPI. Normally it's launched in container as one of the integral parts of SPARA.

## Running Locally

To run the server locally, first ensure you have all necessary dependencies installed. You can install the required Python packages using `pip`:

```
pip install -r requirements.txt
```

Then you need to export .env variables such as:

```
export DB_USER=
export DB_PASSWORD=
export DB_HOST=
export DB_PORT=
export DB_NAME=
```

Once the dependencies are installed, start the server using the following command:

```
uvicorn main:socket_app --reload
```

## Running ReDoc

To run the ReDoc documentation for the API, you can run the server locally as explained in the "Running Locally" section. Then, navigate to `.../redoc` in your web browser to view the API documentation.


## Testing

First, you need to install the testing dependencies in the virtual environment.

In order to create and activate a virtual environment, run the following commands:
```bash
python -m venv venv
source venv/bin/activate
```

Then, install the testing dependencies:
```
pip install -r requirements.txt
```

Then, you can run the tests using `pytest`:

```pytest```

Or to run a specific test file e.g. test for entrypoints:

```pytest /tests/test_entrypoints.py```