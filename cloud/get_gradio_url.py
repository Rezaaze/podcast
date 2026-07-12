#!/usr/bin/env python3
"""Liest 'vastai show instances-v1 --raw' von stdin, sucht die per argv[1]
angegebene Instanz-ID und druckt 'http://ip:port' aus, FALLS Port 7860
bereits gemappt ist -- sonst keine Ausgabe (exit 1). Fuer race.sh, um zu
pruefen, welche Instanz zuerst so weit ist."""
import json
import sys

instance_id = int(sys.argv[1])
data = json.load(sys.stdin)
instances = data.get("instances") or []
d = next((i for i in instances if i.get("id") == instance_id), None)
if d is None:
    sys.exit(1)

ip = d.get("public_ipaddr")
ports = d.get("ports") or {}
port_7860 = ports.get("7860/tcp")
if not ip or not port_7860:
    sys.exit(1)

host_port = port_7860[0].get("HostPort")
if not host_port:
    sys.exit(1)

print(f"http://{ip}:{host_port}")
