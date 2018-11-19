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


def main():
    session = requests.Session()
    session.auth = EdgeGridAuth.from_edgerc(edgerc, section_name)

    zone_json = get_dns_zone(session, 'thewest.com.au')
    
    ts = Terrascript()

    for (rtype, records) in zone_json['zone']:
        if rtype in ('soa', 'nsec3'): continue
        for record in records:
            pass
            #ts.add

if __name__ == '__main__':
    main()

