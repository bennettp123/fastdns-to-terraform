#!/usr/bin/env python

from future.standard_library import install_aliases
install_aliases()

import os
import requests
import json
import argparse
import logging

from urllib.parse import urljoin
from urllib.error import HTTPError

from akamai.edgegrid import EdgeGridAuth, EdgeRc

from terrascript import Terrascript, provider
from terrascript.aws.r import aws_route53_record
from terrascript.aws.d import aws_route53_zone

logger = logging.getLogger(__name__)

edgerc_file = os.environ.get('AKAMAI_EDGERC', os.path.expanduser('~/.edgerc'))
section_name = os.environ.get('AKAMAI_EDGERC_SECTION', 'default')

edgerc = EdgeRc(edgerc_file)
baseurl = 'https://{}'.format(edgerc.get(section_name, 'host'))


def _GET_JSON_(session, path):
    return _GET_(session, path).json()


def _GET_(session, path):
    url = urljoin(baseurl, path)
    response = session.get(url)
    response.raise_for_status()
    return response


def get_dns_zone(session, zone):
    path = '/config-dns/v1/zones/{}'.format(zone)
    return _GET_JSON_(session, path)


ignored = ('id', 'time', 'version', 'name', 'instance', 'publisher')
ignored_rrtypes = ('SOA', 'NSEC3', 'DS', 'DNSKEY', 'NSEC3PARAM')


def main():
    parser = argparse.ArgumentParser(
            description='Fetch FastDNS zone and convert to terraform JSON.')
    parser.add_argument('zone', help='The zone to fetch from FastDNS')
    args = parser.parse_args()

    session = requests.Session()
    session.auth = EdgeGridAuth.from_edgerc(edgerc, section_name)

    zone_json = get_dns_zone(session, args.zone)
    zone_name = zone_json['zone']['name']
    
    ts = Terrascript()

    zone = aws_route53_zone(zone_name.replace('.', '_'),
            name=zone_name)
    ts.add(zone)

    for (rrtype, records) in ((t, r) for (t, r) in zone_json['zone'].items()
            if not t in ignored):
        rrtype = rrtype.upper()
        if rrtype in ignored_rrtypes:
            logger.debug('ignored record type {}'.format(rrtype))
            continue
        if records and rrtype not in ('A', 'AAAA', 'NS', 'CNAME', 'TXT', 'LOC',
                'MX', 'HINFO', 'PTR', 'SRV'):
            logger.warning('unhandled rrtype {}'.format(rrtype))
            continue
        for name in set(x['name'] for x in records):
            resource_name = '{}_{}_{}'.format(name, zone_name, rrtype)
            resource_name = resource_name.replace('.', '_')
            record_name = '.'.join(x for x in (name, zone_name) if x)
            try:
                record_values = [
                        ' '.join(
                            str(s) for s in (x['priority'], x['target']) if s)
                        for x in records if x['name'] == name]
            except KeyError:
                record_values = [
                        x['target']
                        for x in records if x['name'] == name]
            record_ttl = min(x['ttl'] for x in records if x['name'] == name)
            ts.add(aws_route53_record(resource_name,
                type=rrtype, name=record_name, zone_id=zone.zone_id,
                ttl=record_ttl, records=record_values))

    print(ts.dump())


if __name__ == '__main__':
    main()

