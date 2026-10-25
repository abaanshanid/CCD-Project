FROM public.ecr.aws/lambda/python:3.12

RUN dnf install -y libgomp \
    && dnf clean all

COPY requirements-lambda.txt .

RUN pip install \
    --no-cache-dir \
    -r requirements-lambda.txt

# Store the rembg model inside the container image.
# This prevents every new Lambda instance from downloading it.
ENV U2NET_HOME=/opt/u2net

RUN mkdir -p ${U2NET_HOME} \
    && python -c "from rembg import new_session; new_session('u2net')" \
    && chmod -R a+rX ${U2NET_HOME}

COPY processor.py ${LAMBDA_TASK_ROOT}/processor.py
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/lambda_handler.py
COPY cloud_api.py ${LAMBDA_TASK_ROOT}/cloud_api.py
COPY utilities ${LAMBDA_TASK_ROOT}/utilities

CMD ["lambda_handler.handler"]