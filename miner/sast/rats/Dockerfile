FROM debian:bullseye

ENV RATS_COMMIT 4ba54ce278e9fb004d978e924fd63c29e449ca81

RUN apt-get update && \
	apt-get install -y git vim build-essential libexpat1-dev

RUN git clone https://github.com/andrew-d/rough-auditing-tool-for-security.git rats && \
	cd rats && \
	git checkout $RATS_COMMIT && \
	./configure && \
	make && \
	make install

COPY execute.sh /usr/local/bin

ENTRYPOINT execute.sh
