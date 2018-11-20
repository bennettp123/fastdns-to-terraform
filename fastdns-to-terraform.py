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


def _get_json(session, baseurl, path=''):
    '''Fetch a request and parse the response as json.'''
    return _get(session, baseurl, path).json()


def _get(session, baseurl, path=''):
    '''Fetch and return a request. Throws on HTTP 4xx or HTTP 5xx.'''
    url = urljoin(baseurl, path)
    response = session.get(url)
    response.raise_for_status()
    return response


def get_dns_zone(session, baseurl, zone):
    '''Fetch a DNS zone from the FastDNS API. Returns a dict describing the zone.'''
    path = '/config-dns/v1/zones/{}'.format(zone)
    return _get_json(session, baseurl, path)


def _make_aws_route53_record_resource(
        resource_name, zone, rrtype, record_name, records):

    '''Return an aws_route53_record for a zone/rrtype/recordname/records'''

    record_ttl = min(x['ttl'] for x in records)
    
    try:
        record_values = [
                ' '.join(str(s) for s in (x['priority'], x['target']) if s)
                for x in records]
    except KeyError:
        # 'priority' is only valid for some record types (eg MX)
        record_values = [x['target'] for x in records]

    return aws_route53_record(resource_name, type=rrtype, name=record_name,
            zone_id=zone.zone_id, ttl=record_ttl, records=record_values)


# FastDNS api smooshes the records and metadata into the same object. We want
# to remove all of the metadata, and some of the record types too.
ignored_metadata = ('id', 'time', 'version', 'name', 'instance', 'publisher')
ignored_rrtypes = ('SOA', 'NSEC3', 'DS', 'DNSKEY', 'NSEC3PARAM')


def main():
    argparser = argparse.ArgumentParser(
            description='Fetch FastDNS zone and convert to terraform JSON.')
    argparser.add_argument('zone', help='The zone to fetch from FastDNS')
    args = argparser.parse_args()

    # set up an authenenticated session to the FastDNS API
    session = requests.Session()
    session.auth = EdgeGridAuth.from_edgerc(edgerc, section_name)

    # fetch zone from FastDNS
    zone_json = get_dns_zone(session, baseurl, args.zone)
    zone_name = zone_json['zone']['name']
    
    ts = Terrascript()

    zone = aws_route53_zone(zone_name.replace('.', '_'),
            name=zone_name)
    ts.add(zone)

    # filter out the keys we don't need, and convert rrtypes to uppercase
    zone_items = ((t.upper(), r) for (t, r) in zone_json['zone'].items()
            if not t in ignored_metadata)

    for (rrtype, records) in zone_items:

        if rrtype in ignored_rrtypes:
            logger.debug('ignored record type {}'.format(rrtype))
            continue

        if records:
            if rrtype not in ('A', 'AAAA', 'NS', 'CNAME', 'TXT', 'LOC',
                    'MX', 'HINFO', 'PTR', 'SRV'):
                logger.warning('unhandled rrtype {}'.format(rrtype))
                continue

        for name in set(x['name'] for x in records):
            resource_name = '{}_{}_{}'.format(name, zone_name, rrtype)
            resource_name = resource_name.replace('.', '_')
            record_name = '.'.join(x for x in (name, zone_name) if x)

            current_records = [x for x in records if x['name'] == name]
            
            resource = _make_aws_route53_record_resource(
                    resource_name, zone, rrtype, record_name, current_records)

            ts.add(resource)

    print(ts.dump())


if __name__ == '__main__':
    main()


