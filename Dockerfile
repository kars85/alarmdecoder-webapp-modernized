FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

ENV FLASK_APP=ad2web.app:create_app
ENV FLASK_ENV=production
EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]
