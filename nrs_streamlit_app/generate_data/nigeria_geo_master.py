import pandas as pd

NIGERIA_GEO = {
    "Lagos": [
        "Ikeja", "Eti-Osa", "Alimosho", "Surulere", "Lagos Island",
        "Kosofe", "Agege", "Ifako-Ijaiye", "Mushin", "Oshodi-Isolo"
    ],
    "Abuja (FCT)": [
        "Abuja Municipal", "Gwagwalada", "Kuje", "Bwari", "Abaji", "Kwali"
    ],
    "Rivers": [
        "Port Harcourt", "Obio-Akpor", "Ikwerre", "Eleme", "Okrika"
    ],
    "Oyo": [
        "Ibadan North", "Ibadan South-West", "Egbeda", "Akinyele"
    ],
    "Kano": [
        "Kano Municipal", "Nasarawa", "Gwale", "Tarauni"
    ],
    "Ogun": [
        "Abeokuta South", "Abeokuta North", "Sagamu", "Ijebu Ode"
    ],
    "Anambra": [
        "Awka South", "Onitsha North", "Nnewi North", "Idemili South"
    ],
    "Delta": [
        "Warri South", "Uyo", "Sapele", "Ughelli North"
    ],
    "Kaduna": [
        "Kaduna North", "Kaduna South", "Zaria", "Kafanchan"
    ],
    "Edo": [
        "Oredo", "Ikpoba-Okha", "Egor"
    ],
    "Enugu": [
        "Enugu North", "Nsukka", "Udi"
    ],
    "Kwara": [
        "Ilorin West", "Ilorin East", "Offa"
    ],
    "Akwa Ibom": [
        "Uyo", "Eket", "Ikot Ekpene"
    ],
    "Plateau": [
        "Jos North", "Jos South", "Barkin Ladi"
    ]
}

rows = []
for state, lgas in NIGERIA_GEO.items():
    for lga in lgas:
        rows.append({
            "state": state,
            "lga": lga,
            "country": "Nigeria"
        })

geo_df = pd.DataFrame(rows)
geo_df.to_csv("nigeria_geo_master.csv", index=False)
