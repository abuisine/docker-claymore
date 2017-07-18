FROM abuisine/nvidia:17.04-375.66

LABEL maintainer="Alexandre Buisine <alexandrejabuisine@gmail.com>"

RUN DEBIAN_FRONTEND=noninteractive apt-get -qq update \
 && apt-get install -yqq --no-install-recommends \
	vim-tiny \
	flip \
	libcurl4-openssl-dev \
	libcurl3 \
 && apt-get -yqq clean \
 && rm -rf /var/lib/apt/lists/*

ENV CLAYMORE_VERSION="9.7"

ENV GPU_LIST="0"

WORKDIR /home/claymore
ADD https://github.com/nanopool/Claymore-Dual-Miner/releases/download/v${CLAYMORE_VERSION}/Claymore.s.Dual.Ethereum.Decred_Siacoin_Lbry_Pascal.AMD.NVIDIA.GPU.Miner.v${CLAYMORE_VERSION}.-.LINUX.tar.gz .
RUN flip -u *.bash \
 && echo "POOL: eu1.ethermine.org:4444, WALLET: 0x8d3c63a5121d346642e83b69a57a959abfb73812, PSW: x, ESM: 1, ALLPOOLS: 0" > epools.txt \
 && echo "POOL: eu2.ethermine.org:4444, WALLET: 0x8d3c63a5121d346642e83b69a57a959abfb73812, PSW: x, ESM: 1, ALLPOOLS: 0" >> epools.txt

ENV GPU_FORCE_64BIT_PTR=0 GPU_MAX_HEAP_SIZE=100 GPU_USE_SYNC_OBJECTS=1 GPU_MAX_ALLOC_PERCENT=100 GPU_SINGLE_ALLOC_PERCENT=100

COPY resources/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/*

ENV ADDRESS_WALLET="0x8d3c63a5121d346642e83b69a57a959abfb73812.FuriousMiner"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["-mode", "1", "-ftime", "10"]