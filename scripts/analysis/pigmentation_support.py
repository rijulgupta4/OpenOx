"""Summarize measured-pigmentation support in authorized local OpenOx data."""

from pathlib import Path
import numpy as np
import pandas as pd

from src.paths import PROJECT_ROOT


R = PROJECT_ROOT / "data" / "external" / "openoximetry"
C = PROJECT_ROOT / "data" / "processed" / "analytic_cohort_180s.csv.gz"
co = pd.read_csv(C, dtype={"patient_id": str, "encounter_id": str})
en = pd.read_csv(R / "encounter.csv", dtype={"patient_id": str, "encounter_id": str})
sp = pd.read_csv(R / "spectrophotometer.csv", dtype={"patient_id": str, "encounter_id": str})
letters = {chr(65+i): i+1 for i in range(10)}
en["mst"] = en["monk_forehead"].astype("string").str.upper().map(letters)
en["mst_group"] = pd.cut(en.mst, [0,4,7,10], labels=["1-4","5-7","8-10"])
agg = sp.assign(
    lab_l=pd.to_numeric(sp.lab_l, errors="coerce"), lab_b=pd.to_numeric(sp.lab_b, errors="coerce")
)
agg["ita"] = np.degrees(np.arctan((agg.lab_l-50)/agg.lab_b))
agg = agg.groupby(["patient_id","encounter_id","group"], as_index=False).ita.median()
wide = agg.pivot(index=["patient_id","encounter_id"], columns="group", values="ita").reset_index()
df = co.merge(en[["patient_id","encounter_id","mst","mst_group"]], on=["patient_id","encounter_id"], how="left", validate="many_to_one")
df = df.merge(wide, on=["patient_id","encounter_id"], how="left", validate="many_to_one")
loc = df.inferred_assignment_location.astype("string")
df["sensor_site"] = np.where(loc.str.startswith("finger", na=False), "Dorsal (B)", np.where(loc.eq("forehead").fillna(False), "Forehead (E)", pd.NA))
df["sensor_ita"] = np.where(df.sensor_site.eq("Dorsal (B)"), df["Dorsal (B)"], np.where(df.sensor_site.eq("Forehead (E)"), df["Forehead (E)"], np.nan))
df["band"] = np.where(df.so2.between(70,85,inclusive="both"), "70-85", np.where((df.so2>85)&(df.so2<=100),">85-100",pd.NA))

print("ROW COVERAGE")
for c in ["mst","sensor_ita","Forehead (E)","Dorsal (B)"]:
    print(c, df[c].notna().sum(), df[c].notna().mean(), df.loc[df[c].notna(),"patient_id"].nunique(), df.loc[df[c].notna(),"encounter_id"].nunique())
print("MST GROUP SUPPORT")
print(df.dropna(subset=["mst_group"]).groupby("mst_group", observed=True).agg(rows=("mst_group","size"),participants=("patient_id","nunique"),encounters=("encounter_id","nunique")).to_string())
print("SITE MAPPING")
print(df.groupby("sensor_site",dropna=False).agg(rows=("sensor_site","size"),ita_rows=("sensor_ita","count"),participants=("patient_id","nunique")).to_string())

core = (df[df.so2.between(70,100)].groupby("device_probe_key").agg(rows=("so2","size"),patients=("patient_id","nunique"),
    low=("so2",lambda x: ((x>=70)&(x<80)).sum()),mid=("so2",lambda x: ((x>=80)&(x<90)).sum()),high=("so2",lambda x: ((x>=90)&(x<=100)).sum())).reset_index())
core = core[(core.patients>=30)&(core.rows>=300)&(core.low>=50)&(core.mid>=50)&(core.high>=50)]
print("CORE", len(core), core.device_probe_key.tolist())
rows=[]
for key in core.device_probe_key:
    g=df[df.device_probe_key.eq(key)&df.so2.between(70,100)]
    r={"key":key,"patients":g.patient_id.nunique(),"mst_cov":g.mst.notna().mean(),"ita_cov":g.sensor_ita.notna().mean(),"ita_min":g.sensor_ita.min(),"ita_max":g.sensor_ita.max()}
    for m in ["1-4","5-7","8-10"]:
        h=g[g.mst_group.astype("string").eq(m)]
        r[f"p_{m}"]=h.patient_id.nunique(); r[f"n_{m}"]=len(h)
        r[f"lo_{m}"]=((h.so2>=70)&(h.so2<=85)).sum(); r[f"hi_{m}"]=((h.so2>85)&(h.so2<=100)).sum()
    rows.append(r)
out=pd.DataFrame(rows)
print(out.round(2).to_string(index=False))

e = en[["patient_id","encounter_id","fitzpatrick","monk_fingernail","monk_dorsal","monk_palmar","monk_upper_arm","monk_forehead"]].copy()
for c in [x for x in e if x.startswith("monk_")]: e[c]=e[c].astype("string").str.upper().map(letters)
ew = e.merge(wide,on=["patient_id","encounter_id"],how="left")
print("AGREEMENT CORRS")
for a,b in [("fitzpatrick","monk_forehead"),("fitzpatrick","Forehead (E)"),("monk_forehead","Forehead (E)"),("monk_dorsal","Dorsal (B)"),("monk_forehead","monk_dorsal")]:
    z=ew[[a,b]].apply(pd.to_numeric,errors="coerce").dropna()
    print(a,b,len(z),z[a].corr(z[b],method="spearman"))
