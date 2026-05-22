FROM python:3.10-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./backend_app /code/backend_app

CMD ["uvicorn", "backend_app.main:app", "--host", "0.0.0.0", "--port", "8000"]