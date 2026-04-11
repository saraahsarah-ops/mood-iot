FROM python:3.9-slim

WORKDIR /app

COPY ./configuration/api/requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY ./api .

ENV FLASK_APP=app.py
ENV FLASK_ENV=development

EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]
