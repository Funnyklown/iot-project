# Read the doc: https://huggingface.co/docs/hub/spaces-sdks-docker
# you will also find guides on how best to write your Dockerfile

FROM python:3.9
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app


COPY --chown=user ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade --timeout 100 -r requirements.txt

COPY --chown=user . /app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
