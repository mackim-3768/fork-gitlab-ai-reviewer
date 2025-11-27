FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt gunicorn

COPY . .

EXPOSE 9655

CMD ["gunicorn", "--bind", "0.0.0.0:9655", "--timeout", "6000", "src.main:app"]
