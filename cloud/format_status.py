#!/usr/bin/env python3
"""Liest 'vastai show instances-v1 --raw' von stdin, sucht die per argv[1]
angegebene Instanz-ID heraus und druckt Status, GPU/Preis und (falls schon
gemappt) die oeffentliche Gradio-Adresse fuer episodes.json aus."""
import json
import sys

data = json.load(sys.stdin)
instances = data.get("instances") or []
instance_id = int(sys.argv[1])
d = next((i for i in instances if i.get("id") == instance_id), None)
if d is None:
    print(f"Instanz {instance_id} nicht (mehr) gefunden — evtl. noch am Registrieren "
          f"oder bereits gestoppt/gelöscht.")
    sys.exit(0)

print(f"Status:      {d.get('actual_status', '?')}  (status_msg: {d.get('status_msg', '').strip()})")
print(f"GPU:         {d.get('gpu_name', '?')}")
print(f"$/hr:        {d.get('dph_total', '?')}")

ip = d.get("public_ipaddr") or d.get("public_ip") or "?"
ports = d.get("ports") or {}
port_7860 = ports.get("7860/tcp")

if port_7860:
    host_port = port_7860[0].get("HostPort", "?")
    url = f"http://{ip}:{host_port}"
    print(f"Gradio-URL:  {url}")
    print()
    print("In episodes.json eintragen:")
    print(f'  "audio": {{ "backend": "gradio", "api_url": "{url}", ... }}')
else:
    print("Port 7860 noch nicht gemappt (Instanz evtl. noch am Hochfahren) — Rohdaten unten:")
    print(json.dumps(d.get("ports", {}), indent=2))
