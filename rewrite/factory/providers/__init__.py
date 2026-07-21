"""factory.providers — konkrete Modell-Adapter hinter dem Model-Protokoll (§10.8).

Getrennt von core/authoring, weil hier echte Dependencies leben (`anthropic`-SDK).
Der Authoring-Pfad bleibt stdlib-rein und bekommt eine Model-Instanz injiziert — er
importiert dieses Paket nie direkt.
"""
