import os
import pandas as pd
import numpy as np
from datetime import datetime
from faker import Faker

# ---------------- CONFIG ----------------
fake = Faker("en_GB")
CHUNK_SIZE = 10000
TOTAL_INDIVIDUALS = 200_000
TOTAL_COMPANIES = 2000
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------- LOAD GEO MASTER ----------------
geo_df = pd.read_csv("nigeria_geo_master.csv")

def pick_state_lga():
    row = geo_df.sample(1).iloc[0]
    return row["state"], row["lga"]

# ---------------- NAMES & BUSINESSES ----------------
NIGERIAN_FIRST_NAMES = [
    "Ahmed","Sadiq","Musa","Ibrahim","Abdul","Yusuf","Sule","Kabiru",
    "Emeka","Chinedu","Ifeanyi","Uche","Obinna","Nnamdi",
    "Adewale","Oluwaseun","Babajide","Sola","Tunde","Kehinde",
    "Abdulrahman","Ismail","Bashir","Sadiq","Godwin","Osagie",
    "Somtochukwu","Ifezue","Odunayo","Eweniyi","Joshua","Chibueze",
    "Nonso","Easle","Ayo","Akinola","Seyi","Badmus","Kayode","Dedayo"
]

NIGERIAN_LAST_NAMES = [
    "Adeyemi","Olawale","Ogunleye","Adebayo","Olatunji","Ajayi","Balogun",
    "Okafor","Okeke","Eze","Nwankwo","Obi","Onyekachi","Chukwu",
    "Abdullahi","Sadiq","Mohammed","Bello","Musa","Lawal",
    "Oghene","Ebi","Preye","Tamuno","Peters","Johnson","Williams",
    "Eweniyi","Chibueze","Ifezue","Badmus","Dedayo"
]

def generate_nigerian_name():
    first = np.random.choice(NIGERIAN_FIRST_NAMES)
    last = np.random.choice(NIGERIAN_LAST_NAMES)
    if np.random.rand() < 0.25:
        return f"{last} {first}"
    return f"{first} {last}"

NIGERIAN_BUSINESSES = [
    "Zenith Bank", "GTBank", "Access Bank", "First Bank", "UBA", "Union Bank",
    "PiggyVest","MTN","Glovo","OPay","Palmpay","Kuda","Sterling Bank","Moniepoint",
    "Flutterwave","Paystack","Semicolon Africa", "Dangote","Oando","BUA","Globacom","MTN","Airtel","Interswitch",
    "Flutterwave","Paystack","Moniepoint","Kuda","Opay","Palmpay",
    "Zenith","GTCO","Access","UBA","FBN","Stanbic","Sterling",
    "TotalEnergies","Seplat","NLNG","Eroton","Ardova",
    "Shoprite","Spar","Jumia","Konga","Slot","Pointek",
    "Chi","Nestle","Cadbury","SevenUp","Nigerian Breweries",
    "Honeywell","Flour Mills","Dangote Sugar","BUA Cement",
    "ABC Transport","Peace Mass","GIG Logistics",
    "Ibeto","Coscharis","Elizade","Mikano",
    "MainOne","Rack Centre","Galaxy Backbone",
    "Semicolon","Andela","Decagon","AltSchool",
    "Filmhouse","Silverbird","Genesis Group"
]

BUSINESS_DESCRIPTORS = ["Holdings","Industries","Enterprises","Ventures","Resources",
                        "Logistics","Technologies","Systems","Networks","Solutions",
                        "Services","Global","Nigeria","West Africa","Group"]

DEFAULT_INDUSTRY_SECTORS = ["Tech","Fintech","Agro","Manufacturing","Energy","Retail"]

TRANSACTION_CATEGORIES = {
    "Food": "Outflow","Restaurant": "Outflow","Insurance": "Outflow",
    "Healthcare": "Outflow","Transportation": "Outflow","Clothing": "Outflow",
    "Debt Repayment": "Outflow","Entertainment": "Outflow","Education": "Outflow",
    "Medicals": "Outflow","Salary": "Inflow","Gift": "Inflow",
    "Investment": "Inflow","Rent": "Inflow"
}

BUSINESS_TAX_TYPES = ["CIT","VAT","WHT","CGT"]
INDIVIDUAL_TAX_TYPES = ["PIT"]

ENTITY_DOMAINS = {
    "PLC": [".com.ng", ".ng"],
    "Ltd": [".com.ng", ".net.ng"],
    "LLP": [".com.ng"],
    "NGO/Gte": [".org.ng", ".ng"]
}

def generate_company_website(name, entity_type):
    domain = np.random.choice(ENTITY_DOMAINS.get(entity_type, [".com.ng"]))
    base = name.lower().replace(" ", "").replace(",", "")
    return f"www.{base}{domain}"

# ---------------- TAX ENGINE ----------------
def calculate_nrs_pit_2026(gross_income, annual_rent=0):
    pension = gross_income * 0.08
    rent_relief = min(annual_rent * 0.20, 500_000)
    taxable_income = gross_income - pension - rent_relief
    if taxable_income <= 800_000: return 0
    bands = [(2_200_000,0.15),(9_000_000,0.18),(13_000_000,0.21),(25_000_000,0.23)]
    tax, remaining = 0, taxable_income-800_000
    for limit, rate in bands:
        portion = min(limit, remaining)
        tax += portion * rate
        remaining -= portion
        if remaining <= 0: return tax
    return tax + (remaining*0.25)

# ---------------- AML FLAG UTILS ----------------
def generate_aml_flags_for_individual(uid, income, declared_income, transactions, assets, relationships):
    aml_flags = []

    # Income Gap
    if declared_income < (0.5*income):
        aml_flags.append({
            "aml_id": fake.uuid4(),
            "entity_id": uid,
            "entity_type": "Individual",
            "reason": "Income Gap",
            "risk_level": "High",
            "created_date": datetime.now().strftime("%d-%b-%Y")
        })

    # High-Value Transactions (>₦10M) and Structuring
    for txn in transactions:
        if txn["transaction_type"] == "Outflow" and txn["amount"] > 10_000_000:
            aml_flags.append({
                "aml_id": fake.uuid4(),
                "entity_id": uid,
                "entity_type": "Individual",
                "reason": "High-Value Transaction",
                "risk_level": "High",
                "created_date": datetime.now().strftime("%d-%b-%Y")
            })
        if txn["transaction_type"] == "Outflow" and 9_000_000 <= txn["amount"] <= 10_000_000:
            aml_flags.append({
                "aml_id": fake.uuid4(),
                "entity_id": uid,
                "entity_type": "Individual",
                "reason": "Structuring / Smurfing",
                "risk_level": "Medium",
                "created_date": datetime.now().strftime("%d-%b-%Y")
            })

    # Asset-Income Mismatch
    for asset in assets:
        if asset["estimated_value"] > 5 * declared_income:
            aml_flags.append({
                "aml_id": fake.uuid4(),
                "entity_id": uid,
                "entity_type": "Individual",
                "reason": "Asset-Income Mismatch",
                "risk_level": "High",
                "created_date": datetime.now().strftime("%d-%b-%Y")
            })

    # Multiple Directorships
    director_count = sum(1 for r in relationships if r["relationship_role"]=="Director")
    if director_count > 2:
        aml_flags.append({
            "aml_id": fake.uuid4(),
            "entity_id": uid,
            "entity_type": "Individual",
            "reason": "Multiple Directorships",
            "risk_level": "Medium",
            "created_date": datetime.now().strftime("%d-%b-%Y")
        })

    # PEP Status Random Tag
    if np.random.rand() < 0.001:
        aml_flags.append({
            "aml_id": fake.uuid4(),
            "entity_id": uid,
            "entity_type": "Individual",
            "reason": "PEP Status",
            "risk_level": "High",
            "created_date": datetime.now().strftime("%d-%b-%Y")
        })

    return aml_flags

def generate_aml_flags_for_company(company):
    aml_flags = []

    # High Turnover, No Tax Paid
    if company["declared_turnover"] > 50_000_000 and company["cit_due"] == 0:
        aml_flags.append({
            "aml_id": fake.uuid4(),
            "entity_id": company["company_id"],
            "entity_type": "Company",
            "reason": "High Turnover No Tax Paid",
            "risk_level": "High",
            "created_date": datetime.now().strftime("%d-%b-%Y")
        })
    # Profit-Turnover Anomaly
    if company["estimated_profit"] > company["declared_turnover"]*0.5:
        aml_flags.append({
            "aml_id": fake.uuid4(),
            "entity_id": company["company_id"],
            "entity_type": "Company",
            "reason": "Profit-Turnover Anomaly",
            "risk_level": "Medium",
            "created_date": datetime.now().strftime("%d-%b-%Y")
        })
    # Payroll vs Turnover
    if company["payroll_estimate"] < 0.05*company["declared_turnover"]:
        aml_flags.append({
            "aml_id": fake.uuid4(),
            "entity_id": company["company_id"],
            "entity_type": "Company",
            "reason": "Payroll vs Turnover Mismatch",
            "risk_level": "High",
            "created_date": datetime.now().strftime("%d-%b-%Y")
        })
    # VAT Under-Reporting
    expected_vat = company["declared_turnover"] * 0.075
    if company["vat_paid"] < 0.5 * expected_vat:
        aml_flags.append({
            "aml_id": fake.uuid4(),
            "entity_id": company["company_id"],
            "entity_type": "Company",
            "reason": "VAT Under-Reporting",
            "risk_level": "High",
            "created_date": datetime.now().strftime("%d-%b-%Y")
        })
    # Turnover per Employee Anomaly
    tpe = company["declared_turnover"]/company["staff_strength"]
    if tpe > 10_000_000:
        aml_flags.append({
            "aml_id": fake.uuid4(),
            "entity_id": company["company_id"],
            "entity_type": "Company",
            "reason": "Turnover per Employee Anomaly",
            "risk_level": "High",
            "created_date": datetime.now().strftime("%d-%b-%Y")
        })
    return aml_flags

# ---------------- MAIN GENERATOR ----------------
def generate_full_nrs_suite():

    # -------- BANKS --------
    banks = pd.DataFrame([{
        "institution_id": fake.uuid4(),
        "name": b,
        "license_type": np.random.choice([
            "Retail Bank", "Digital Bank", "Microfinance Institution", "Loan Company"
        ]),
        "compliance_score": np.random.randint(70, 99)
    } for b in NIGERIAN_BUSINESSES if "Bank" in b or b in ["OPay","Kuda","Palmpay","Moniepoint","Flutterwave","Paystack"]])
    banks.to_csv(os.path.join(OUTPUT_DIR, "banks_financial.csv"), index=False)

    # -------- COMPANIES --------
    company_names_set = set()
    companies = []
    while len(companies) < TOTAL_COMPANIES:
        state, lga = pick_state_lga()
        root = np.random.choice(NIGERIAN_BUSINESSES)
        descriptor = np.random.choice(BUSINESS_DESCRIPTORS)
        suffix = np.random.choice(["Ltd","PLC","LLP","NGO/Gte"])
        name = f"{root} {descriptor} {suffix}"
        if name in company_names_set: continue
        company_names_set.add(name)

        turnover = np.random.uniform(5_000_000, 5_000_000_000)
        declared_turnover = turnover * np.random.uniform(0.5,1.0)
        estimated_profit = turnover * np.random.uniform(0.08,0.25)
        staff_strength = np.random.randint(5,1200)
        payroll_estimate = staff_strength * np.random.uniform(30_000, 500_000)
        vat_paid = declared_turnover * np.random.uniform(0.0,0.075)
        founded = fake.date_between("-15y", "today")
        entity_type = suffix

        # Use business descriptor as industry sector, fallback to default list
        industry_sector = descriptor if descriptor in DEFAULT_INDUSTRY_SECTORS else np.random.choice(DEFAULT_INDUSTRY_SECTORS)

        companies.append({
            "company_id": fake.uuid4(),
            "registration_number": f"RC-{np.random.randint(100000,999999)}",
            "tin": "".join(str(np.random.randint(0,9)) for _ in range(13)),
            "name": name,
            "industry_sector": industry_sector,
            "entity_type": entity_type,
            "turnover": turnover,
            "declared_turnover": declared_turnover,
            "estimated_profit": estimated_profit,
            "cit_due": 0 if declared_turnover < 50_000_000 else declared_turnover * 0.30,
            "development_levy_due": 0 if declared_turnover < 100_000_000 else declared_turnover * 0.04,
            "staff_strength": staff_strength,
            "payroll_estimate": payroll_estimate,
            "vat_paid": vat_paid,
            "founded_date": founded.strftime("%d-%b-%Y"),
            "founded_year": founded.year,
            "last_audit_date": fake.date_between("-2y","today").strftime("%d-%b-%Y"),
            "state": state,
            "lga": lga,
            "website": generate_company_website(name, entity_type),
            "applicable_taxes": ",".join(BUSINESS_TAX_TYPES)
        })

    df_companies = pd.DataFrame(companies)
    df_companies.to_csv(os.path.join(OUTPUT_DIR, "companies.csv"), index=False)

    # -------- COMPANY AML FLAGS --------
    company_flags = []
    for _, company in df_companies.iterrows():
        company_flags.extend(generate_aml_flags_for_company(company))
    pd.DataFrame(company_flags).to_csv(os.path.join(OUTPUT_DIR, "aml_flags_companies.csv"), index=False)

    # -------- CHUNKED INDIVIDUALS --------
    for i in range(0, TOTAL_INDIVIDUALS, CHUNK_SIZE):
        individuals, taxes, transactions = [], [], []
        assets, relationships, aml_flags, spend_events = [], [], [], []

        for _ in range(CHUNK_SIZE):
            uid = fake.uuid4()
            income = np.random.uniform(500_000, 250_000_000)
            declared_income = income * np.random.uniform(0.4, 1.0)

            state_res, lga_res = pick_state_lga()
            state_org, lga_org = pick_state_lga()
            pit = calculate_nrs_pit_2026(income, income*0.15)
            paid = pit
            compliance = round((paid/pit)*100 if pit>0 else 100,2)
            full_name = generate_nigerian_name()

            individuals.append({
                "individual_id": uid,
                "full_name": full_name,
                "phone": fake.phone_number(),
                "occupation": fake.job(),
                "state_of_origin": state_org,
                "origin_lga": lga_org,
                "state_of_residence": state_res,
                "residence_lga": lga_res,
                "national_id_number": "".join(str(np.random.randint(0,9)) for _ in range(11)),
                "bvn": "".join(str(np.random.randint(0,9)) for _ in range(11)),
                "tin": "".join(str(np.random.randint(0,9)) for _ in range(13)),
                "declared_income": declared_income,
                "estimated_income": income,
                "hni_badge": income>50_000_000,
                "risk_score": np.random.randint(20,90)
            })

            taxes.append({
                "tax_entry_id": fake.uuid4(),
                "entity_id": uid,
                "tax_type": "PIT",
                "YOA": np.random.randint(2022,2026),
                "calculated_amount": pit,
                "paid_amount": paid,
                "outstanding_balance": max(0,pit-paid),
                "tax_station": lga_res,
                "compliance_percent": compliance
            })

            # ----- Generate transactions, spend_events, assets, relationships only for this individual -----
            indiv_transactions, indiv_spend_events, indiv_assets, indiv_relationships = [], [], [], []

            # Transactions & spend_events
            for _ in range(np.random.randint(3,6)):
                cat = np.random.choice(list(TRANSACTION_CATEGORIES.keys()))
                amt = 4_950_000 if cat=="Gift" and np.random.rand()<0.03 else np.random.uniform(1_000,5_000_000)
                indiv_transactions.append({
                    "transaction_id": fake.uuid4(),
                    "source_id": uid,
                    "amount": amt,
                    "category": cat,
                    "transaction_type": TRANSACTION_CATEGORIES[cat],
                    "tax_status": "Taxable" if cat in ["Salary","Investment","Rent"] else "Exempt",
                    "payment_channel": np.random.choice(["Bank","POS","OPay","USSD"]),
                    "date": fake.date_this_year().strftime("%d-%b-%Y")
                })
                indiv_spend_events.append({
                    "event_id": fake.uuid4(),
                    "individual_id": uid,
                    "category": cat,
                    "amount": amt,
                    "state": state_res,
                    "lga": lga_res
                })

                # Assets
            for _ in range(np.random.randint(1, 3)):
                indiv_assets.append({
                    "asset_id": fake.uuid4(),
                    "owner_id": uid,
                    "asset_type": np.random.choice(["Car", "House", "Land", "Yacht", "SUV"]),
                    "estimated_value": np.random.uniform(5_000_000, 800_000_000)
                })

                # Relationships
            for _ in range(np.random.randint(1, 3)):
                target_comp = df_companies.sample(1).iloc[0]
                role = "Director" if income > 50_000_000 else "Employee"
                indiv_relationships.append({
                    "relationship_id": fake.uuid4(),
                    "subject_id": uid,
                    "subject_type": "Individual",
                    "object_id": target_comp["company_id"],
                    "object_type": "Company",
                    "relationship_role": role,
                    "start_date": target_comp["founded_date"],
                    "status": "Active"
                })
                indiv_relationships.append({
                    "relationship_id": fake.uuid4(),
                    "subject_id": uid,
                    "subject_type": "Individual",
                    "object_id": target_comp["company_id"],
                    "object_type": "Company",
                    "relationship_role": "Customer",
                    "start_date": target_comp["founded_date"],
                    "status": "Active"
                })

                # Append this individual's data to main lists
            transactions.extend(indiv_transactions)
            spend_events.extend(indiv_spend_events)
            assets.extend(indiv_assets)
            relationships.extend(indiv_relationships)

            # AML flags only check new transactions/assets for this individual
            aml_flags.extend(generate_aml_flags_for_individual(
                uid, income, declared_income, indiv_transactions, indiv_assets, indiv_relationships
            ))

            # -------- WRITE CHUNK TO CSV --------
        tables = {
            "individuals.csv": individuals,
            "taxes.csv": taxes,
            "transactions.csv": transactions,
            "aml_flags.csv": aml_flags,
            "spend_events.csv": spend_events,
            "assets.csv": assets,
            "relationships.csv": relationships
        }

        for name, data in tables.items():
            if data:  # only write if list is non-empty
                pd.DataFrame(data).to_csv(
                    os.path.join(OUTPUT_DIR, name),
                    mode="a",
                    header=not os.path.exists(os.path.join(OUTPUT_DIR, name)),
                    index=False
                )

        print(f"✅ Chunk {(i // CHUNK_SIZE) + 1} complete")

        # -------- SPEND AGGREGATES --------
    spend_events_path = os.path.join(OUTPUT_DIR, "spend_events.csv")
    if os.path.exists(spend_events_path):
        se = pd.read_csv(spend_events_path)
        agg = se.groupby(["state", "lga", "category"]).agg(
            total_amount=("amount", "sum"),
            transaction_count=("amount", "count")
        ).reset_index()
        agg.to_csv(os.path.join(OUTPUT_DIR, "spend_aggregates.csv"), index=False)
        print("✅ Spend aggregates generated")


# ---------------- RUN ----------------
if __name__ == "__main__":
    generate_full_nrs_suite()
    print("✅ NRS 2026 DATA HUB – COMPLETE")

