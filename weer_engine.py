# -*- coding: utf-8 -*-
"""weer_engine.py - de weermotor van DraveWeer.

Gratis weergegevens via Open-Meteo (geen API-sleutel nodig):
- stad zoeken (geocoding)
- huidig weer, 7-daagse verwachting en uurverwachting

Alles met de Python-standaardbibliotheek (urllib), dus geen extra installaties.
"""
import json
import urllib.parse
import urllib.request

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FC_URL = "https://api.open-meteo.com/v1/forecast"

# WMO-weercodes -> (nederlandse omschrijving, icoon-categorie)
# icoon-categorieen: zon, halfbewolkt, bewolkt, mist, motregen, regen, sneeuw,
#                    buien, onweer
WMO = {
    0: ("Helder", "zon"),
    1: ("Overwegend helder", "halfbewolkt"),
    2: ("Half bewolkt", "halfbewolkt"),
    3: ("Bewolkt", "bewolkt"),
    45: ("Mistig", "mist"),
    48: ("Mist met rijp", "mist"),
    51: ("Lichte motregen", "motregen"),
    53: ("Motregen", "motregen"),
    55: ("Dichte motregen", "motregen"),
    56: ("Lichte ijzel", "motregen"),
    57: ("IJzel", "motregen"),
    61: ("Lichte regen", "regen"),
    63: ("Regen", "regen"),
    65: ("Zware regen", "regen"),
    66: ("Lichte ijsregen", "regen"),
    67: ("IJsregen", "regen"),
    71: ("Lichte sneeuw", "sneeuw"),
    73: ("Sneeuw", "sneeuw"),
    75: ("Zware sneeuw", "sneeuw"),
    77: ("Sneeuwkorrels", "sneeuw"),
    80: ("Lichte buien", "buien"),
    81: ("Buien", "buien"),
    82: ("Zware buien", "buien"),
    85: ("Lichte sneeuwbuien", "sneeuw"),
    86: ("Sneeuwbuien", "sneeuw"),
    95: ("Onweer", "onweer"),
    96: ("Onweer met lichte hagel", "onweer"),
    99: ("Onweer met hagel", "onweer"),
}

DAGEN = ["ma", "di", "wo", "do", "vr", "za", "zo"]


def beschrijf(code):
    """Geef (omschrijving, icoon-categorie) voor een WMO-code."""
    try:
        return WMO.get(int(code), ("Wisselend", "bewolkt"))
    except Exception:
        return ("Onbekend", "bewolkt")


def _get(url, params, timeout=10):
    q = url + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(q, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def zoek_plaats(naam, aantal=8):
    """Zoek plaatsen op naam. Geeft een lijst met dicts terug:
    {naam, regio, land, lat, lon}."""
    naam = (naam or "").strip()
    if not naam:
        return []
    try:
        data = _get(GEO_URL, {"name": naam, "count": aantal, "language": "nl",
                              "format": "json"})
    except Exception:
        return []
    out = []
    for r in (data.get("results") or []):
        out.append({
            "naam": r.get("name", naam),
            "regio": r.get("admin1", "") or "",
            "land": r.get("country", "") or "",
            "lat": r.get("latitude"),
            "lon": r.get("longitude"),
        })
    return out


def haal_weer(lat, lon):
    """Haal huidig weer + 7-daagse + uurverwachting (24u) op.
    Geeft een dict terug, of None bij mislukken."""
    try:
        data = _get(FC_URL, {
            "latitude": lat, "longitude": lon, "timezone": "auto",
            "forecast_days": 7,
            "current": ",".join([
                "temperature_2m", "apparent_temperature", "relative_humidity_2m",
                "weather_code", "wind_speed_10m", "wind_direction_10m", "is_day"]),
            "hourly": ",".join([
                "temperature_2m", "precipitation_probability", "weather_code"]),
            "daily": ",".join([
                "weather_code", "temperature_2m_max", "temperature_2m_min",
                "precipitation_probability_max", "sunrise", "sunset"]),
        })
    except Exception:
        return None

    cur = data.get("current") or {}
    oms, icoon = beschrijf(cur.get("weather_code"))
    huidig = {
        "temp": cur.get("temperature_2m"),
        "gevoel": cur.get("apparent_temperature"),
        "vocht": cur.get("relative_humidity_2m"),
        "wind": cur.get("wind_speed_10m"),
        "windricht": cur.get("wind_direction_10m"),
        "dag": bool(cur.get("is_day", 1)),
        "oms": oms, "icoon": icoon,
    }

    # uurverwachting: vanaf nu, 24 uur vooruit
    hourly = data.get("hourly") or {}
    tijden = hourly.get("time") or []
    nu = (data.get("current") or {}).get("time", "")
    start = 0
    for i, t in enumerate(tijden):
        if t >= nu:
            start = i
            break
    uur = []
    temps = hourly.get("temperature_2m") or []
    regenk = hourly.get("precipitation_probability") or []
    codes = hourly.get("weather_code") or []
    for i in range(start, min(start + 24, len(tijden))):
        _, ic = beschrijf(codes[i] if i < len(codes) else 0)
        uur.append({
            "tijd": tijden[i][11:16],          # HH:MM
            "temp": temps[i] if i < len(temps) else None,
            "regen": regenk[i] if i < len(regenk) else None,
            "icoon": ic,
        })

    # 7-daagse
    daily = data.get("daily") or {}
    dtijden = daily.get("time") or []
    dmax = daily.get("temperature_2m_max") or []
    dmin = daily.get("temperature_2m_min") or []
    dcode = daily.get("weather_code") or []
    dregen = daily.get("precipitation_probability_max") or []
    import datetime
    dagen = []
    for i, d in enumerate(dtijden):
        oms_d, ic_d = beschrijf(dcode[i] if i < len(dcode) else 0)
        try:
            wd = datetime.date.fromisoformat(d).weekday()
            label = DAGEN[wd]
        except Exception:
            label = d[5:]
        dagen.append({
            "datum": d, "dag": label,
            "max": dmax[i] if i < len(dmax) else None,
            "min": dmin[i] if i < len(dmin) else None,
            "regen": dregen[i] if i < len(dregen) else None,
            "oms": oms_d, "icoon": ic_d,
        })

    zon = daily.get("sunrise") or []
    onder = daily.get("sunset") or []
    huidig["op"] = zon[0][11:16] if zon else ""
    huidig["onder"] = onder[0][11:16] if onder else ""

    return {"huidig": huidig, "uur": uur, "dagen": dagen}


if __name__ == "__main__":
    # snelle test vanaf de opdrachtregel
    plaatsen = zoek_plaats("Breda")
    print("Gevonden:", [p["naam"] + ", " + p["land"] for p in plaatsen[:3]])
    if plaatsen:
        p = plaatsen[0]
        w = haal_weer(p["lat"], p["lon"])
        h = w["huidig"]
        print("Nu in %s: %s graden, %s, wind %s km/u" %
              (p["naam"], round(h["temp"]), h["oms"], round(h["wind"])))
        print("Morgen:", w["dagen"][1])
        print("Eerste uur:", w["uur"][0])
