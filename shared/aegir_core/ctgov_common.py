"""ClinicalTrials.gov helpers both tools use: the data timestamp, personal-data stripping, history-index parsing."""

API = "https://clinicaltrials.gov/api/v2"


def data_timestamp(ctx):
    """Registry data timestamp (one request per process, cached)."""
    if "ctgov_ts" not in ctx.cache:
        ctx.cache["ctgov_ts"] = None
        r = ctx.client.get(f"{API}/version")
        if r is not None and r.ok:
            try:
                ctx.cache["ctgov_ts"] = r.json().get("dataTimestamp")
            except ValueError:
                pass
    return ctx.cache["ctgov_ts"]


def strip_personal(study):
    """Remove names, emails and phones (R11). Returns True if anything was removed."""
    changed = False
    ps = study.get("protocolSection", {})
    cl = ps.get("contactsLocationsModule")
    if isinstance(cl, dict):
        for k in ("centralContacts", "overallOfficials"):
            if k in cl:
                del cl[k]
                changed = True
        for loc in cl.get("locations", []) or []:
            if isinstance(loc, dict) and "contacts" in loc:
                del loc["contacts"]
                changed = True
    rp = ps.get("sponsorCollaboratorsModule", {}).get("responsibleParty")
    if isinstance(rp, dict):
        for k in ("investigatorFullName", "investigatorTitle", "investigatorAffiliation"):
            if k in rp:
                del rp[k]
                changed = True
    return changed


def parse_index(obj):
    """[(version, date, module_labels)] from a history index; tolerant of key naming."""
    items = obj.get("changes") if isinstance(obj, dict) else obj
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        v = it.get("version", it.get("versionNumber"))
        d = it.get("date") or it.get("versionDate") or ""
        if v is not None:
            out.append((int(v), str(d)[:10], it.get("moduleLabels") or []))
    return sorted(out)
