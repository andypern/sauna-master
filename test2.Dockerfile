FROM arm32v6/python:3.11-alpine
WORKDIR /app

RUN apk update && apk add --no-cache \
    build-base \
    bash \
    git \
    && rm -rf /var/cache/apk/*

RUN pip3 install streamlit boto3 s3fs streamlit_pdf_viewer vastdb pandas trino OpenAI markdown numpy duckdb pymilvus ibis
COPY app/* /app/

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]