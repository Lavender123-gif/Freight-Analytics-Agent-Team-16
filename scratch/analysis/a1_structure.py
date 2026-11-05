"""Structured-field facts on the dev split (aggregates only)."""

from common import EPS, load_dev

df = load_dev()
n = len(df)
print(f"rows {n}, shipments {df.SHIPMENT_GID.nunique()}, carriers {df.carrier.nunique()}")

# Delta identity
diff = (df["Invoice Amount"] - df["Shipment Amount"] - df["Delta"]).abs()
print(f"Delta != Invoice - Shipment (>{EPS}): {(diff > EPS).sum()}")

# Delta sign
print(f"Delta > 0: {(df.Delta > EPS).sum()}, == 0: {(df.Delta.abs() <= EPS).sum()}, < 0: {(df.Delta < -EPS).sum()}")

# US/CAN
print("US/CAN values:", df["US/CAN"].value_counts().to_dict())
ca = {"AB", "BC", "SK", "MB", "ON", "QC", "NS", "NB", "NL", "PE"}
dest_ca = df["Destination State"].isin(ca)
src_ca = df["Source State"].isin(ca)
print(f"destination in Canadian province: {dest_ca.sum()} ({dest_ca.mean():.1%})")
print(f"source in Canadian province: {src_ca.sum()} ({src_ca.mean():.1%})")
print(f"cross-border (exactly one end in Canada): {(dest_ca ^ src_ca).sum()}")
print("destination state:", df["Destination State"].value_counts().to_dict())

# PK
print(f"PK empty: {df.PK.isna().sum()} ({df.PK.isna().mean():.1%}); distinct PK {df.PK.nunique()}")
pk_sizes = df.dropna(subset=["PK"]).groupby("PK").size()
print("rows per PK:", pk_sizes.value_counts().sort_index().to_dict())
pk_ship = df.dropna(subset=["PK"]).groupby("PK").SHIPMENT_GID.nunique()
print(f"PKs spanning >1 shipment: {(pk_ship > 1).sum()}")
same = (df["PK"].str.replace("PPGTM.", "", regex=False) == df["Invoice/Bill ID"]) | df.PK.isna()
print(f"PK == 'PPGTM.' + Invoice/Bill ID (or both empty): {same.sum()} / {n}")

# Shipment / carrier invoice
print("rows per shipment:", df.groupby("SHIPMENT_GID").size().value_counts().sort_index().to_dict())
print(f"Carrier Invoice distinct per shipment >1: {(df.groupby('SHIPMENT_GID')['Carrier Invoice'].nunique() > 1).sum()}")
print(f"Carrier Invoice spanning >1 shipment: {(df.groupby('Carrier Invoice').SHIPMENT_GID.nunique() > 1).sum()}")

# Invoice Dups Removed
idr = df["Invoice Dups Removed"]
print(
    f"Invoice Dups Removed == Invoice Amount: {(abs(idr - df['Invoice Amount']) <= EPS).sum()}, "
    f"== 0: {(idr.abs() <= EPS).sum()}, other: {((abs(idr - df['Invoice Amount']) > EPS) & (idr.abs() > EPS)).sum()}"
)

# Status and reason code
print("Dispute Status:", df["Dispute Status"].value_counts().to_dict())
print("Reason Code:", df["Reason Code"].value_counts().to_dict())
print(f"Reason Code = OTHER_ACCESSORIALS share: {(df['Reason Code'] == 'PPGTM.INCORRECT_MISSING_OTHER_ACCESSORIALS').mean():.1%}")

# Text presence
print(f"empty description: {(df.text_norm == '').sum()}; distinct non-empty texts {df.loc[df.text_norm != '', 'text_norm'].nunique()}")

# Carrier concentration
vc = df.carrier.value_counts()
print("rows by carrier:", vc.to_dict())
print(f"top carrier share {vc.iloc[0] / n:.1%}; top 3 share {vc.iloc[:3].sum() / n:.1%}")

# Event date range
print("Event Date range:", df["Event Date"].min(), "to", df["Event Date"].max())
print("Event month counts:", df["Event Date"].str[:7].value_counts().sort_index().to_dict())

# Dispute Status by carrier (is DECLINED concentrated?)
print("DECLINED rows by carrier:", df[df["Dispute Status"].str.endswith("DECLINED")].carrier.value_counts().to_dict())
print("DECLINED Event month:", df[df["Dispute Status"].str.endswith("DECLINED")]["Event Date"].str[:7].value_counts().sort_index().to_dict())
