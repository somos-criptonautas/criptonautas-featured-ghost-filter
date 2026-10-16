# syntax=docker/dockerfile:1.7
# Stage 1: download the weights (pinned by SHA-256) and export them to ONNX. Not part of the final image.
FROM python:3.13-slim AS models
RUN pip install --no-cache-dir numpy==2.5.3 onnx==1.23.2
WORKDIR /build
ADD --checksum=sha256:c686ced2a666b4850b4bb6ccf0748031c3eda9f822de73a34b8979970d90f0c6 \
    https://huggingface.co/lllyasviel/Annotators/resolve/main/sk_model.pth sk_model.pth
ADD --checksum=sha256:30a534781061f34e83bb9406b4335da4ff2616c95d22a585c1245aa8363e74e0 \
    https://huggingface.co/lllyasviel/Annotators/resolve/main/sk_model2.pth sk_model2.pth
COPY torch_weights.py line_art.py ./
RUN python -c "import onnx; from line_art import build_onnx_model; \
onnx.save(build_onnx_model('sk_model.pth'), 'stroke_thin.onnx'); \
onnx.save(build_onnx_model('sk_model2.pth'), 'stroke_thick.onnx')"

# Stage 2: runtime image, only what serving needs.
FROM python:3.13-slim
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /app
COPY --chmod=0444 brand_filter.py line_art.py server.py ./
COPY --from=models /build/stroke_thin.onnx /build/stroke_thick.onnx ./models/
USER 65534:65534
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["python", "server.py"]
