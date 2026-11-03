"""Turn the AACT pipe-delimited export into a few parquet files for offline training and testing. Never shipped, never fetched.

    python tools/aact_workbench.py "<AACT export folder>" "<output folder>"

Writes studies.parquet (one row per study), text.parquet (summary, description, eligibility), agg.parquet (sponsor, design, counts per study)
and flow.parquet (participant-flow recruitment text). Standard pandas and pyarrow only. The two huge result tables are not read.
"""
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

CHUNK = 250_000


def read(path, usecols=None):
    return pd.read_csv(path, sep="|", usecols=usecols, dtype=str, chunksize=CHUNK, low_memory=False, on_bad_lines="error")


def write_chunks(src, dst, usecols=None):
    w, n = None, 0
    for ch in read(src, usecols):
        t = pa.Table.from_pandas(ch, preserve_index=False)
        w = w or pq.ParquetWriter(dst, t.schema, compression="zstd")
        w.write_table(t)
        n += len(ch)
    w.close()
    return n


def main(src, out):
    src, out = Path(src), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    n = write_chunks(src / "studies.txt", out / "studies.parquet")
    print("studies", n, round(time.time() - t0))

    # text: three one-to-one tables on nct_id
    txt = None
    for name, col, new in [("brief_summaries", "description", "brief_summary"), ("detailed_descriptions", "description", "detailed_description")]:
        d = pd.concat(read(src / f"{name}.txt", ["nct_id", col])).drop_duplicates("nct_id").rename(columns={col: new})
        txt = d if txt is None else txt.merge(d, on="nct_id", how="outer")
    el = pd.concat(read(src / "eligibilities.txt", ["nct_id", "criteria", "population", "gender", "minimum_age", "maximum_age", "healthy_volunteers", "sampling_method"])).drop_duplicates("nct_id")
    txt = txt.merge(el.rename(columns={"criteria": "eligibility_criteria", "population": "study_population"}), on="nct_id", how="outer")
    txt.to_parquet(out / "text.parquet", compression="zstd", index=False)
    print("text", len(txt), round(time.time() - t0))
    del txt, el

    # aggregates
    sp = pd.concat(read(src / "sponsors.txt", ["nct_id", "agency_class", "lead_or_collaborator", "name"]))
    lead = sp[sp.lead_or_collaborator == "lead"].drop_duplicates("nct_id").rename(columns={"agency_class": "lead_class", "name": "lead_name"})[["nct_id", "lead_class", "lead_name"]]
    ncol = sp[sp.lead_or_collaborator != "lead"].groupby("nct_id").size().rename("n_collaborators").reset_index()
    des = pd.concat(read(src / "designs.txt", ["nct_id", "allocation", "intervention_model", "primary_purpose", "masking", "time_perspective"])).drop_duplicates("nct_id")
    cv = pd.concat(read(src / "calculated_values.txt")).drop(columns=["id", "nlm_download_date"]).drop_duplicates("nct_id")
    agg = lead.merge(ncol, on="nct_id", how="outer").merge(des, on="nct_id", how="outer").merge(cv, on="nct_id", how="outer")
    lists = {"conditions": "name", "keywords": "name", "countries": "name"}
    for tbl, col in lists.items():
        acc = defaultdict(list)
        for ch in read(src / f"{tbl}.txt", ["nct_id", col] + (["removed"] if tbl == "countries" else [])):
            if tbl == "countries":
                ch = ch[ch.removed != "t"]
            for k, v in zip(ch.nct_id, ch[col]):
                acc[k].append(v) if isinstance(v, str) else None
        agg = agg.merge(pd.Series({k: "; ".join(v[:30]) for k, v in acc.items()}, name=tbl).rename_axis("nct_id").reset_index(), on="nct_id", how="left")
    types = defaultdict(set)
    for ch in read(src / "interventions.txt", ["nct_id", "intervention_type"]):
        for k, v in zip(ch.nct_id, ch.intervention_type):
            types[k].add(v)
    agg = agg.merge(pd.Series({k: "; ".join(sorted(v)) for k, v in types.items()}, name="intervention_types").rename_axis("nct_id").reset_index(), on="nct_id", how="left")
    fac = Counter()
    for ch in read(src / "facilities.txt", ["nct_id"]):
        fac.update(ch.nct_id)
    agg = agg.merge(pd.Series(fac, name="n_facility_rows").rename_axis("nct_id").reset_index(), on="nct_id", how="left")
    agg.to_parquet(out / "agg.parquet", compression="zstd", index=False)
    print("agg", len(agg), round(time.time() - t0))

    write_chunks(src / "participant_flows.txt", out / "flow.parquet", ["nct_id", "recruitment_details", "pre_assignment_details"])
    print("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main(*sys.argv[1:3])
