FROM python:3-alpine as build
ADD . /work
RUN pip install wheel build
RUN cd /work && python -m build -w

FROM python:3-alpine
COPY --from=build /work/dist/*.whl /
RUN pip install /*.whl
ENTRYPOINT ["qrgen"]
