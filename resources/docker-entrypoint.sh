#!/usr/bin/env bash
set -eo pipefail

exec /home/claymore/ethdcrminer64 -ewal ${ADDRESS_WALLET} -di ${GPU_LIST} $@