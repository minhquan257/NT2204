FROM public.ecr.aws/lambda/python:3.12-arm64

COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.8.0 torchvision==0.23.0
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt \
    && pip uninstall -y opencv-python \
    && pip install --no-cache-dir opencv-python-headless==4.12.0.88

COPY yolov8n.pt ${LAMBDA_TASK_ROOT}/yolov8n.pt
COPY handler.py ${LAMBDA_TASK_ROOT}/handler.py

CMD ["handler.handler"]
