FROM public.ecr.aws/lambda/python:3.9

# 1. Install system dependencies (including ATLAS for BLAS/LAPACK)
RUN yum update -y && \
    yum install -y \
      wget \
      bzip2 \
      tar \
      which \
      atlas-sse3-devel \
      lapack-devel \
      bzip2-devel \
      xz-devel \
      zlib-devel \
      pcre2-devel \
      libicu-devel \
      readline-devel \
      libXt-devel \
      libX11-devel \
      libjpeg-devel \
      libpng-devel \
      libtiff-devel \
      curl-devel \
      libcurl-devel \
      pcre-devel && \
    yum groupinstall -y "Development Tools" && \
    yum clean all

# 2. Build and install R from source, letting configure auto-find ATLAS BLAS/LAPACK
WORKDIR /usr/src
RUN wget https://cran.r-project.org/src/base/R-4/R-4.3.3.tar.gz && \
    tar -xzf R-4.3.3.tar.gz && \
    cd R-4.3.3 && \
    ./configure \
      --enable-R-shlib \
      --with-readline \
      --with-x \
      --with-libpng \
      --with-jpeglib \
      --with-tiff \
      --with-blas \
      --with-lapack && \
    make -j$(nproc) && \
    make install && \
    cd .. && \
    rm -rf R-4.3.3 R-4.3.3.tar.gz

RUN Rscript -e "install.packages(c('mvtnorm','modeltools', 'coin'), repos='https://cloud.r-project.org')"

ENV LD_LIBRARY_PATH=/usr/local/lib64/R/lib:/usr/local/lib64:$LD_LIBRARY_PATH

# 3. Upgrade pip/setuptools/wheel, then install Python packages (including rpy2)
RUN pip install --upgrade pip setuptools wheel && \
    pip install \
      awslambdaric \
      botocore \
      boto3 \
      pydantic \
      pydantic_settings \
      "numpy==1.24.3" \
      "pandas==2.2.3" \
      scipy \
      matplotlib \
      scikit-learn \
      biom-format \
      h5py \
      "rpy2==3.5.10" \
      requests

# 4. Install LEfSe into the Lambda root if still needed
WORKDIR /tmp
RUN wget https://anaconda.org/bioconda/lefse/1.1.2/download/noarch/lefse-1.1.2-pyhdfd78af_0.tar.bz2 && \
    mkdir lefse-conda-tmp && \
    tar -xvjf lefse-1.1.2-pyhdfd78af_0.tar.bz2 -C lefse-conda-tmp && \
    LAMBDA_SITE=$(python -c "import site; print(site.getsitepackages()[0])") && \
    cp -r lefse-conda-tmp/site-packages/lefse "$LAMBDA_SITE/" && \
    cp -r lefse-conda-tmp/site-packages/lefse-1.1.2.dist-info "$LAMBDA_SITE/" && \
    cp -r lefse-conda-tmp/site-packages/lefsebiom "$LAMBDA_SITE/" && \
    cp lefse-conda-tmp/python-scripts/*.py ${LAMBDA_TASK_ROOT}/ && \
    rm -rf lefse-conda-tmp lefse-1.1.2-pyhdfd78af_0.tar.bz2

# 5. Set environment and copy your Lambda handler
COPY config.py ${LAMBDA_TASK_ROOT}/
COPY global-bundle.pem ${LAMBDA_TASK_ROOT}/
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/
COPY lefse_preprocessing.py ${LAMBDA_TASK_ROOT}/
COPY submit_results.py ${LAMBDA_TASK_ROOT}/

# 6. Set up local testing needs
ADD https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie \
    /usr/local/bin/aws-lambda-rie
RUN chmod +x /usr/local/bin/aws-lambda-rie

WORKDIR ${LAMBDA_TASK_ROOT}

# Create an entrypoint script for local testing
RUN echo '#!/bin/bash' > /entrypoint.sh && \
    echo 'if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then' >> /entrypoint.sh && \
    echo '    exec /usr/local/bin/aws-lambda-rie python3 -m awslambdaric $1' >> /entrypoint.sh && \
    echo 'else' >> /entrypoint.sh && \
    echo '    exec python3 -m awslambdaric $1' >> /entrypoint.sh && \
    echo 'fi' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]


# Set the CMD to your handler
CMD ["lambda_function.lambda_handler"]
