FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive

ENV HOME=/container \
    PATH="/usr/local/conda/bin:/container/pypy3.6-v7.3.3-linux64/bin:$PATH"
    
# Add labels
LABEL AUTHOR="ellisk@mit.edu"
LABEL CORRECTED_BY = "oyeluckydps@gmail.com"

RUN apt-get update && \
    apt-get -y install python3 git wget m4 libcairo2-dev libzmq3-dev swig graphviz && \
    mkdir /container && \
    chmod 777 /container && \
    mkdir /container/ec && \
    chmod 777 /container/ec 

RUN wget https://repo.continuum.io/miniconda/Miniconda3-py37_4.9.2-Linux-x86_64.sh && \
    chmod +x Miniconda3-py37_4.9.2-Linux-x86_64.sh && \
    ./Miniconda3-py37_4.9.2-Linux-x86_64.sh -b -p /usr/local/conda && \
    rm ./Miniconda3-py37_4.9.2-Linux-x86_64.sh

ENV PATH="/usr/local/conda/bin:$PATH"

COPY . /container/ec

#RUN cd /container/ && \
#    git clone https://github.com/ellisk42/ec && \
#    chmod 777 /container/ec

RUN apt-get -y install gcc g++ && \
    pip install -r /container/ec/requirements.txt && \
    pip install pycairo==1.20.1 && \
    pip install git+https://github.com/MaxHalford/vose@fae179e5afa45f224204519c10957d087633ae60

RUN wget https://downloads.python.org/pypy/pypy3.6-v7.3.3-linux64.tar.bz2 && \
    tar xjvf pypy3.6-v7.3.3-linux64.tar.bz2 && \
    rm pypy3.6-v7.3.3-linux64.tar.bz2 && \
    mv pypy3.6-v7.3.3-linux64 /container && \
    pypy3 -m ensurepip && \
    pypy3 -m pip install vmprof dill psutil frozendict numpy pathos

#Put the Opam code here.
RUN apt-get install -y software-properties-common && \
    apt update && \
    apt install -y nano opam  && \
    opam init --disable-sandboxing -a --root /container/.opam  && \
    opam update  && \
    opam switch create 4.06.1+flambda  && \
    eval $(opam env)  && \
    opam install -y  ppx_jane core re2 yojson vg cairo2 camlimages menhir ocaml-protoc zmq utop jbuilder

RUN echo '\
#use "topfind";;\n\
#thread;;\n\
#require "core.top";;\n\
#require "core.syntax";;\n\
open Core;;\n\
' >> /container/.ocamlinit

RUN echo 'eval `opam config env`' >> /root/.bashrc

# Set working directory
WORKDIR /container/ec

# Set the entrypoint to use OPAM's environment
ENTRYPOINT ["opam", "config", "exec", "--"]

# Default command to run in the container
CMD ["bash"]
