FROM debian:bullseye

ENV CPPCHECK_COMMIT f4cfed674c20e6991e3726b7e275cf96fc965b29

RUN apt-get update && \
	apt-get install -y git vim build-essential python3 libpcre++-dev

RUN git clone https://github.com/danmar/cppcheck.git cppcheck && \
	cd cppcheck && \
	git checkout $CPPCHECK_COMMIT && \
	make install MATCHCOMPILER=yes FILESDIR=/usr/share/cppcheck HAVE_RULES=yes CXXFLAGS="-O2 -DNDEBUG -Wall -Wno-sign-compare -Wno-unused-function"

COPY execute.sh /usr/local/bin

ENTRYPOINT execute.sh
