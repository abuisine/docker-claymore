import socket
import logging
import json

from prometheus_client import CollectorRegistry, Gauge, Counter, push_to_gateway
from prometheus_client import start_http_server, core
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY

from pynvml import *

log = logging.getLogger('claymore-exporter')

def launch(args, metadata, gpu_uuid_short):

	if 'eth-wallet-address' in metadata['labels']:
		wallet_address = metadata['labels']['eth-wallet-address']
	else:
		wallet_address = os.environ['WALLET_ADDRESS']
	log.info('ETH wallet address is %s', wallet_address)

	miner_config_filename = '/home/claymore/eepools.txt'
	miner_config = open(miner_config_filename, 'w')
	for host in os.environ['HOSTS'].split(' '):
		host_name, host_port, password, esm, allpools = host.split(':')

		miner_config.write("POOL: %s:%s, WALLET: %s.GPU-%s, PSW: %s, ESM: %s, ALLPOOLS: %s\n"%(host_name, host_port, wallet_address, gpu_uuid_short, password, esm, allpools))

	miner_config.close()
	log.info('launching miner in process %d', os.getpid())
	os.execl('/home/claymore/ethdcrminer64', 'ethdcrminer64', '-mport', "-%d"%args.miner_port, '-mode', '1', '-ftime', '10')

class MinerCollector:
	API_CALL_GETSTAT = {'id':0, 'jsonrpc':"2.0", 'method':"miner_getstat1"}

	# [u'9.8 - ETH', u'949', u'26642;328;0', u'26642', u'0;0;0', u'off', u'64;48', u'eu1.ethermine.org:4444', u'0;0;0;0']
	CLAYMORE_API_RESULT_VERSION				= 0
	CLAYMORE_API_RESULT_UPTIME				= 1
	CLAYMORE_API_RESULT_ETH_SHARES_TOTAL	= 2
	CLAYMORE_API_RESULT_ETH_SHARES_ONE		= 3
	CLAYMORE_API_RESULT_DCH_SHARES_TOTAL	= 4
	CLAYMORE_API_RESULT_DCH_SHARES_ONE		= 5
	CLAYMORE_API_RESULT_TEMP_FAN			= 6
	CLAYMORE_API_RESULT_POOLS				= 7
	CLAYMORE_API_RESULT_EVENTS				= 8

	def __init__(self, labels, hostname, port):
		self.labels		= labels
		self.hostname	= hostname
		self.port		= port

		self.prefix		= 'claymore_'
		self.prefix_s	= 'Claymore '

	def getAPIStat(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			log.debug('connecting to miner ...')
			s.connect((self.hostname, self.port))
			log.debug('sending signing request to the miner')
			s.sendall(json.dumps(self.API_CALL_GETSTAT))
			log.debug('waiting for miner response')
			response = s.recv(10 * 1024)
			log.debug('parsing JSON response')
			stat = json.loads(response)
		except socket.error as e:
			log.info('miner not available: %s', e)
			return None
		finally:
			s.close()
		return stat['result']

	def collect(self):
		stat = self.getAPIStat()

		if ( not stat ):
			return

		try:
			#LABELS
			self.labels['version'] = stat[self.CLAYMORE_API_RESULT_VERSION]

			pools_s = stat[self.CLAYMORE_API_RESULT_POOLS].split(';', 2)
			self.labels['eth_pool_current'] = pools_s[0]
			# self.labels['dcr_pool_current'] = pools_s[1] if len(pools_s) >= 2 else None

			#COUNTERS
			metric = CounterMetricFamily(self.prefix + 'uptime_minutes', self.prefix_s + "uptime", labels=self.labels.keys())
			metric.add_metric(self.labels.values(), float(stat[self.CLAYMORE_API_RESULT_UPTIME]))
			yield metric

			eth_shares_invalid, eth_pool_switches, dcr_shares_invalid, dcr_pool_switches = stat[self.CLAYMORE_API_RESULT_EVENTS].split(';', 4)
			metric = CounterMetricFamily(self.prefix + 'eth_shares_invalid', self.prefix_s + "ETH invalid shares", labels=self.labels.keys())
			metric.add_metric(self.labels.values(), float(eth_shares_invalid))
			yield metric
			metric = CounterMetricFamily(self.prefix + 'eth_pool_switches', self.prefix_s + "ETH pool swithes", labels=self.labels.keys())
			metric.add_metric(self.labels.values(), float(eth_pool_switches))
			yield metric

			eth_hashrate_total_mhs, eth_shares_accepted, eth_shares_rejected = stat[self.CLAYMORE_API_RESULT_ETH_SHARES_TOTAL].split(';', 3)
			metric = CounterMetricFamily(self.prefix + 'eth_shares_accepted', self.prefix_s + "ETH accepted shares", labels=self.labels.keys())
			metric.add_metric(self.labels.values(), float(eth_shares_accepted))
			yield metric
			metric = CounterMetricFamily(self.prefix + 'eth_shares_rejected', self.prefix_s + "ETH rejected shares", labels=self.labels.keys())
			metric.add_metric(self.labels.values(), float(eth_shares_rejected))
			yield metric

			#GAUGES
			metric = GaugeMetricFamily(self.prefix + 'eth_hashrate_total_mhs', self.prefix_s + "ETH total hashrate", labels=self.labels.keys())
			metric.add_metric(self.labels.values(), float(eth_hashrate_total_mhs))
			yield metric
			gpu_temperature_c, fan_speed_percent = stat[self.CLAYMORE_API_RESULT_TEMP_FAN].split(';', 2)
			metric = GaugeMetricFamily(self.prefix + 'gpu_temperature_c', self.prefix_s + "GPU temperature", labels=self.labels.keys())
			metric.add_metric(self.labels.values(), float(gpu_temperature_c))
			yield metric
			metric = GaugeMetricFamily(self.prefix + 'fan_speed_percent', self.prefix_s + "GPU fan speed", labels=self.labels.keys())
			metric.add_metric(self.labels.values(), float(fan_speed_percent))
			yield metric

			log.info('collected hashrate:%.1fMHs accepted:%d rejected:%d', float(eth_hashrate_total_mhs), int(eth_shares_accepted), int(eth_shares_rejected))

		except Exception as e:
			log.warning(e, exc_info=True)