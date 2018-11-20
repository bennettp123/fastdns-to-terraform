# fastdns-to-terraform

A quick and dirty script to dump out a FastDNS zone to terraform
`aws_route53_record` resources.


# Requirements

See `requirements.txt`.

Requires Python 3.

While the code should work on both Python 2 and 3, the terrascript library
only works on Python 3.


# Usage

```
fastdns-to-terraform.py zone
```

Uses the `default` section in `~/.edgerc` for auth. This can be customized using
`AKAMAI_EDGERC` and `AKAMAI_EDGERC_SECTION`.

To launch it in docker, you'll need to make sure `.edgerc` is preset:

```
docker build -t fastdns-to-terraform .
docker run --rm -it -v "$HOME/.edgerc:/root/.edgerc:ro" \
  fastdns-to-terraform python fastdns-to-terraform.py zone
```

